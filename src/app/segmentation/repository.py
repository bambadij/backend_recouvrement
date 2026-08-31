from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import case, func, select, true, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.debiteurs.models import Debiteur
from app.creances.models import Creance, StatutCreance
from app.paiements.models import Paiement
from app.promesses.models import Promesse, StatutPromesse
from app.relances.models import Relance, StatutRelance
from app.segmentation.models import Segmentation, SegmentRisque
from app.segmentation.schemas import FaitsDossier

#: Un dossier soldee ou annulee n'a plus rien a recouvrer : le classer serait du
#: bruit dans la file de travail, et de l'appel de modele paye pour rien.
STATUTS_ACTIFS = (StatutCreance.EN_COURS, StatutCreance.EN_RETARD, StatutCreance.LITIGE)

#: Gravite croissante. Sert a elire, parmi les creances d'un meme debiteur,
#: celle qui le represente dans la file de relance.
RANG_SEGMENT = {
    SegmentRisque.FAIBLE: 0,
    SegmentRisque.MOYEN: 1,
    SegmentRisque.ELEVE: 2,
    SegmentRisque.CRITIQUE: 3,
}


def _jours_depuis(reference: date | None, aujourdhui: date) -> int | None:
    return (aujourdhui - reference).days if reference is not None else None


class SegmentationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        return Creance.organisation_id == organisation_id if organisation_id is not None else true()

    async def charger_faits(
        self,
        organisation_id: int | None,
        limite: int,
        inclure_deja_classes: bool = True,
    ) -> list[FaitsDossier]:
        """Rassemble les faits de chaque dossier actif.

        Quatre requetes agregees plutot qu'une par dossier : sur un parc de plusieurs
        centaines de creances, le N+1 couterait plus cher que l'appel de modele qui suit.
        """
        aujourdhui = date.today()

        query = (
            select(Creance, Debiteur)
            .join(Debiteur, Creance.debiteur_id == Debiteur.id)
            .where(self._portee(organisation_id), Creance.statut.in_(STATUTS_ACTIFS))
        )
        if not inclure_deja_classes:
            # Ne reclasse pas ce qui l'a deja ete : la passe quotidienne ne doit
            # payer que les dossiers nouveaux ou modifies.
            query = query.outerjoin(Segmentation, Segmentation.creance_id == Creance.id).where(
                Segmentation.id.is_(None)
            )
        query = query.order_by(Creance.montant_restant.desc()).limit(limite)

        lignes = (await self.db.execute(query)).all()
        if not lignes:
            return []

        creance_ids = [creance.id for creance, _ in lignes]
        couples = [(c.dossier_id, c.debiteur_id) for c, _ in lignes]
        # Les relances visent un debiteur dans un dossier, pas une facture : on
        # agrege sur ce couple puis on redistribue sur ses creances.
        relances = await self._agregats_relances(couples)
        paiements = await self._agregats_paiements(creance_ids)
        promesses = await self._agregats_promesses(couples)

        faits: list[FaitsDossier] = []
        for creance, debiteur in lignes:
            nb_relances, nb_echouees, derniere_relance = relances.get(
                (creance.dossier_id, creance.debiteur_id), (0, 0, None)
            )
            nb_paiements, dernier_paiement = paiements.get(creance.id, (0, None))
            nb_promesses, tenues, rompues = promesses.get(
                (creance.dossier_id, creance.debiteur_id), (0, 0, 0)
            )

            initial = creance.montant_initial or 0
            regle = initial - creance.montant_restant
            taux = int(regle / initial * 100) if initial else 0

            faits.append(
                FaitsDossier(
                    creance_id=creance.id,
                    reference=creance.reference,
                    debiteur=f"{debiteur.prenom} {debiteur.nom}".strip(),
                    entreprise=debiteur.entreprise,
                    etablissement=creance.etablissement,
                    cycle=creance.cycle,
                    financeur=creance.financeur,
                    montant_initial=creance.montant_initial,
                    montant_restant=creance.montant_restant,
                    taux_regle=max(0, min(100, taux)),
                    anciennete_jours=(aujourdhui - creance.date_echeance).days,
                    statut=creance.statut.value,
                    nb_relances=nb_relances,
                    nb_relances_echouees=nb_echouees,
                    jours_depuis_derniere_relance=_jours_depuis(derniere_relance, aujourdhui),
                    nb_paiements=nb_paiements,
                    jours_depuis_dernier_paiement=_jours_depuis(dernier_paiement, aujourdhui),
                    nb_promesses=nb_promesses,
                    nb_promesses_tenues=tenues,
                    nb_promesses_rompues=rompues,
                )
            )
        return faits

    async def _agregats_relances(
        self, couples: list[tuple[int, int]]
    ) -> dict[tuple[int, int], tuple[int, int, date | None]]:
        """Compteurs de relances par (dossier, debiteur) — la maille de relance."""
        result = await self.db.execute(
            select(
                Relance.dossier_id,
                Relance.debiteur_id,
                func.count(),
                func.count().filter(Relance.statut == StatutRelance.ECHOUEE),
                func.max(Relance.date_relance),
            )
            .where(Relance.dossier_id.in_({d for d, _ in couples}))
            .group_by(Relance.dossier_id, Relance.debiteur_id)
        )
        return {(row[0], row[1]): (row[2], row[3], row[4]) for row in result.all()}

    async def _agregats_paiements(self, creance_ids: list[int]) -> dict[int, tuple[int, date | None]]:
        result = await self.db.execute(
            select(Paiement.creance_id, func.count(), func.max(Paiement.date_paiement))
            .where(Paiement.creance_id.in_(creance_ids))
            .group_by(Paiement.creance_id)
        )
        return {row[0]: (row[1], row[2]) for row in result.all()}

    async def _agregats_promesses(
        self, couples: list[tuple[int, int]]
    ) -> dict[tuple[int, int], tuple[int, int, int]]:
        """Compteurs de promesses par (dossier, debiteur) — la meme maille que les relances.

        Une promesse engage un debiteur dans un dossier, pas une facture : c'est
        au telephone qu'elle se prend, et le debiteur promet de payer, pas de
        payer telle ligne. Elle se redistribue donc sur toutes ses creances,
        comme les relances juste au-dessus.
        """
        result = await self.db.execute(
            select(
                Promesse.dossier_id,
                Promesse.debiteur_id,
                func.count(),
                func.count().filter(Promesse.statut == StatutPromesse.TENUE),
                func.count().filter(Promesse.statut == StatutPromesse.ROMPUE),
            )
            .where(Promesse.dossier_id.in_({d for d, _ in couples}))
            .group_by(Promesse.dossier_id, Promesse.debiteur_id)
        )
        return {(row[0], row[1]): (row[2], row[3], row[4]) for row in result.all()}

    async def classement_par_couple(
        self, organisation_id: int | None, couples: list[tuple[int, int]]
    ) -> dict[tuple[int, int], tuple[Segmentation, Creance]]:
        """Le classement ramene a la maille de la file de relance.

        La segmentation classe des CREANCES, la file de travail vise un DEBITEUR
        DANS UN DOSSIER : un seul appel couvre tous ses impayes. Il faut donc
        elire, parmi les creances du couple, celle qui le represente.

        La regle : le pire segment l'emporte, et a segment egal le plus gros
        montant restant. Un debiteur qui paie une facture et pas l'autre est
        range sur celle qu'il ne paie pas — c'est elle qui justifie l'appel, et
        c'est sa justification que l'agent doit lire avant de decrocher.

        L'election se fait en SQL, par DISTINCT ON, et non en Python sur tout le
        portefeuille : la file se recharge a chaque clic de critere, et ramener
        des dizaines de milliers de lignes pour n'en garder qu'une par couple
        coutait cette lecture entiere a chaque fois. Le tri porte la meme regle
        que RANG_SEGMENT, construit depuis lui pour qu'ils ne puissent pas
        diverger.
        """
        if not couples:
            return {}

        rang = case(
            *[(Segmentation.segment == segment, valeur) for segment, valeur in RANG_SEGMENT.items()],
            else_=0,
        )
        result = await self.db.execute(
            select(Segmentation, Creance)
            .join(Creance, Segmentation.creance_id == Creance.id)
            .where(
                self._portee(organisation_id),
                Creance.statut.in_(STATUTS_ACTIFS),
                tuple_(Creance.dossier_id, Creance.debiteur_id).in_(couples),
            )
            .distinct(Creance.dossier_id, Creance.debiteur_id)
            .order_by(
                Creance.dossier_id,
                Creance.debiteur_id,
                rang.desc(),
                Creance.montant_restant.desc(),
            )
        )
        return {
            (creance.dossier_id, creance.debiteur_id): (segmentation, creance)
            for segmentation, creance in result.all()
        }

    async def derniere_passe(self, organisation_id: int | None) -> datetime | None:
        """Quand la derniere passe de classement a tourne, ou None si aucune.

        Une requete a part, et non le maximum des creances elues : une passe qui
        reclasse une facture non elue est bien une passe, et la file doit
        l'annoncer. Sans cela, un administrateur venant de lancer un classement
        lisait une date vieille de trois semaines et croyait son geste sans effet.
        """
        return await self.db.scalar(
            select(func.max(Segmentation.calcule_le))
            .join(Creance, Segmentation.creance_id == Creance.id)
            .where(self._portee(organisation_id))
        )

    async def cartographie(
        self, organisation_id: int | None
    ) -> list[tuple[str, str, int, Decimal]]:
        """Encours ventilé par case (segment de risque x potentiel de recouvrement).

        C'est la vue qui donne son sens aux deux axes : le risque seul dit où ça
        va mal, le croisement dit où l'effort paie. Les cases vides ne sont pas
        renvoyées — le front reconstruit la grille complète.
        """
        result = await self.db.execute(
            select(
                Segmentation.segment,
                Segmentation.potentiel,
                func.count(),
                func.coalesce(func.sum(Creance.montant_restant), 0),
            )
            .join(Creance, Segmentation.creance_id == Creance.id)
            .where(self._portee(organisation_id))
            .group_by(Segmentation.segment, Segmentation.potentiel)
        )
        return [(r[0].value, r[1].value, r[2], Decimal(r[3])) for r in result.all()]

    async def poids_potentiel_par_creance(self, organisation_id: int | None) -> dict[int, str]:
        """Potentiel de recouvrement de chaque créance classée, pour la prévision."""
        result = await self.db.execute(
            select(Segmentation.creance_id, Segmentation.potentiel).where(
                self._portee(organisation_id)
            )
        )
        return {row[0]: row[1].value for row in result.all()}

    async def get_by_creance(self, creance_id: int) -> Segmentation | None:
        """Sans portee : reserve aux appels internes ou l'id vient deja d'une requete cadrée."""
        result = await self.db.execute(select(Segmentation).where(Segmentation.creance_id == creance_id))
        return result.scalar_one_or_none()

    async def get_scoped_by_creance(
        self, creance_id: int, organisation_id: int | None
    ) -> Segmentation | None:
        """Variante cadrée a l'organisation, seule utilisable depuis une route.

        La jointure sur Creance est ce qui porte l'isolation : la table
        segmentations ne stocke pas d'organisation_id propre, donc filtrer
        uniquement sur creance_id laisserait lire le classement d'un autre
        client en devinant un identifiant.
        """
        query = (
            select(Segmentation)
            .join(Creance, Segmentation.creance_id == Creance.id)
            .where(Segmentation.creance_id == creance_id, self._portee(organisation_id))
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def enregistrer(self, segmentations: list[Segmentation]) -> None:
        """Remplace la segmentation courante de chaque creance concernee."""
        for segmentation in segmentations:
            existante = await self.get_by_creance(segmentation.creance_id)
            if existante is not None:
                await self.db.delete(existante)
        await self.db.flush()
        self.db.add_all(segmentations)
        await self.db.commit()

    async def list_dossiers_segmentes(
        self, organisation_id: int | None, limit: int = 200
    ) -> list[tuple[Segmentation, Creance, Debiteur]]:
        query = (
            select(Segmentation, Creance, Debiteur)
            .join(Creance, Segmentation.creance_id == Creance.id)
            .join(Debiteur, Creance.debiteur_id == Debiteur.id)
            .where(self._portee(organisation_id))
            .limit(limit)
        )
        return [(s, c, cl) for s, c, cl in (await self.db.execute(query)).all()]
