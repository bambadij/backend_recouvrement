from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import String, case, cast, func, literal, select, true
from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy.ext.asyncio import AsyncSession

from app.debiteurs.models import Debiteur
from app.creances.models import Creance, StatutCreance
from app.paiements.models import Paiement
from app.creances.schemas import CreanceCreate, CreanceUpdate


class CreanceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour une vue plateforme.

        organisation_id None signifie « toutes les organisations » : le SUPER_ADMIN
        consulte alors le parc entier. Renvoyer true() plutot que d'omettre la clause
        garde la forme des requetes identique dans les deux cas.
        """
        return Creance.organisation_id == organisation_id if organisation_id is not None else true()


    async def create(self, data: CreanceCreate, organisation_id: int | None) -> Creance:
        creance = Creance(
            **data.model_dump(), montant_restant=data.montant_initial, organisation_id=organisation_id
        )
        self.db.add(creance)
        await self.db.commit()
        await self.db.refresh(creance)
        return creance

    async def get_by_id(self, creance_id: int) -> Creance | None:
        return await self.db.get(Creance, creance_id)

    async def soldes_par_dossier_debiteur(
        self, couples: list[tuple[int, int]]
    ) -> dict[tuple[int, int], Decimal]:
        """Solde restant de chaque couple (dossier, debiteur) demande.

        Borne l'extraction des promesses : un engagement ne peut pas porter sur
        plus que ce que ce debiteur doit encore dans ce dossier.
        """
        if not couples:
            return {}
        dossier_ids = {d for d, _ in couples}
        result = await self.db.execute(
            select(
                Creance.dossier_id,
                Creance.debiteur_id,
                func.coalesce(func.sum(Creance.montant_restant), 0),
            )
            .where(Creance.dossier_id.in_(dossier_ids))
            .group_by(Creance.dossier_id, Creance.debiteur_id)
        )
        return {(row[0], row[1]): Decimal(row[2]) for row in result.all()}

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Creance).where(self._portee(organisation_id))
        )
        return int(result.scalar_one())

    async def get_by_reference(self, reference: str, organisation_id: int | None) -> Creance | None:
        result = await self.db.execute(
            select(Creance).where(Creance.reference == reference, self._portee(organisation_id))
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        debiteur_id: int | None = None,
        dossier_id: int | None = None,
        statut: StatutCreance | None = None,
        organisation_id: int | None = None,
    ) -> list[Creance]:
        query = select(Creance)
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
        if debiteur_id is not None:
            query = query.where(Creance.debiteur_id == debiteur_id)
        if dossier_id is not None:
            query = query.where(Creance.dossier_id == dossier_id)
        if statut is not None:
            query = query.where(self._statut_effectif() == statut.value)
        query = query.order_by(Creance.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, creance: Creance, data: CreanceUpdate) -> Creance:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(creance, field, value)
        await self.db.commit()
        await self.db.refresh(creance)
        return creance

    async def appliquer_paiement(self, creance: Creance, montant: Decimal) -> Creance:
        creance.montant_restant -= montant
        if creance.montant_restant <= 0:
            creance.montant_restant = Decimal("0")
            creance.statut = StatutCreance.SOLDEE
        await self.db.commit()
        await self.db.refresh(creance)
        return creance

    async def delete(self, creance: Creance) -> None:
        await self.db.delete(creance)
        await self.db.commit()

    async def count_by_statut(self, organisation_id: int | None) -> dict[str, int]:
        statut = self._statut_effectif()
        result = await self.db.execute(
            select(statut.label("statut"), func.count())
            .where(self._portee(organisation_id))
            .group_by(statut)
        )
        # Le CASE est ramene en texte : les cles sont deja des chaines.
        return {nom: count for nom, count in result.all()}

    async def balance_agee(self, organisation_id: int | None) -> dict[str, tuple[Decimal, int]]:
        """Encours restant dû réparti par ancienneté de retard, agrégé en base.

        Le calcul ne peut pas vivre côté client : il porterait sur la page chargée
        et non sur le portefeuille. Une seule requête, quel que soit le volume.

        Le montant retenu est le restant dû — la balance âgée mesure ce qui n'est
        pas rentré. Les créances soldées ou annulées sont exclues : la première a
        un restant nul, la seconde ne sera jamais encaissée.
        """
        tranche = self._tranche(func.current_date() - Creance.date_echeance)

        result = await self.db.execute(
            select(
                tranche.label("tranche"),
                func.coalesce(func.sum(Creance.montant_restant), 0),
                func.count(),
            )
            .where(
                self._portee(organisation_id),
                Creance.statut.notin_([StatutCreance.SOLDEE, StatutCreance.ANNULEE]),
            )
            .group_by(tranche)
        )
        return {nom: (Decimal(montant), nombre) for nom, montant, nombre in result.all()}

    @staticmethod
    def _statut_effectif():
        """Statut réel d'une créance, retard déduit de la date.

        EN_RETARD n'est jamais écrit en base : rien, ni job ni code applicatif, ne
        fait basculer une créance quand son échéance passe. Le stocker imposerait un
        rafraîchissement quotidien et une fenêtre où la donnée est fausse ; on le
        déduit donc à la lecture, ici, pour que tous les agrégats s'accordent.

        LITIGE, SOLDEE et ANNULEE sont des décisions humaines : le calendrier ne les
        écrase pas.
        """
        # Les deux branches doivent avoir le meme type SQL : la colonne est un enum
        # PostgreSQL, la constante un parametre VARCHAR, et « CASE types statut_creance
        # and character varying cannot be matched ». On ramene tout en texte.
        return case(
            (
                (Creance.statut == StatutCreance.EN_COURS)
                & (Creance.date_echeance < func.current_date()),
                literal(StatutCreance.EN_RETARD.value),
            ),
            else_=cast(Creance.statut, String),
        )

    @staticmethod
    def _tranche(jours):
        """Expression SQL de la tranche d'âge. Partagée pour que la photo du jour et
        l'historique découpent l'axe exactement de la même façon."""
        return case(
            (jours <= 0, "non-echu"),
            (jours <= 30, "1-30"),
            (jours <= 60, "31-60"),
            (jours <= 90, "61-90"),
            else_="90+",
        )

    async def balance_agee_a_date(self, organisation_id: int | None, date_ref: date) -> dict[str, Decimal]:
        """Balance âgée telle qu'elle était à une date passée.

        Reconstruite, pas stockée : le restant dû d'une créance au jour J vaut son
        montant initial moins les paiements encaissés jusqu'à J. Les créances créées
        après J sont hors périmètre, celles déjà soldées à J tombent d'elles-mêmes
        (reste nul, donc écartées).

        Limite assumée : le statut ANNULEE est l'état d'aujourd'hui, pas celui de J.
        Une créance annulée depuis sort aussi des mois passés — l'historique est donc
        légèrement sous-évalué sur ces cas, plutôt que faussement gonflé.
        """
        paye_a_date = (
            select(func.coalesce(func.sum(Paiement.montant), 0))
            .where(Paiement.creance_id == Creance.id, Paiement.date_paiement <= date_ref)
            .correlate(Creance)
            .scalar_subquery()
        )
        reste = Creance.montant_initial - paye_a_date
        tranche = self._tranche(date_ref - Creance.date_echeance)

        result = await self.db.execute(
            select(tranche.label("tranche"), func.coalesce(func.sum(reste), 0))
            .where(
                self._portee(organisation_id),
                Creance.statut != StatutCreance.ANNULEE,
                Creance.date_saisie <= date_ref,
                reste > 0,
            )
            .group_by(tranche)
        )
        return {nom: Decimal(montant) for nom, montant in result.all()}

    async def echeances_a_venir(self, organisation_id: int | None, nb_mois: int) -> dict[str, Decimal]:
        """Montants restant dus, regroupés par mois d'échéance à partir du mois courant.

        Ce n'est pas une prévision : rien n'est extrapolé. C'est le calendrier de ce
        qui devient exigible, mois par mois — d'où le nom.

        Le mois courant n'est compté qu'à partir d'aujourd'hui : une créance échue le
        5 alors qu'on est le 30 n'est pas « à venir », elle est en retard, et c'est la
        balance âgée qui en rend compte.
        """
        mois = func.to_char(Creance.date_echeance, "YYYY-MM")
        result = await self.db.execute(
            select(mois.label("mois"), func.coalesce(func.sum(Creance.montant_restant), 0))
            .where(
                self._portee(organisation_id),
                Creance.statut.notin_([StatutCreance.SOLDEE, StatutCreance.ANNULEE]),
                # A partir d'AUJOURD'HUI, pas du 1er du mois : sinon tout ce qui est
                # deja echu depuis le debut du mois serait compte comme « a venir »,
                # en contradiction avec la tranche « Non echu » de la balance agee.
                Creance.date_echeance >= func.current_date(),
                Creance.date_echeance < func.date_trunc("month", func.current_date())
                + func.cast(func.concat(nb_mois, " months"), INTERVAL),
            )
            .group_by(mois)
            .order_by(mois)
        )
        return {m: Decimal(montant) for m, montant in result.all()}

    async def resume_par_organisation(self) -> dict[int, tuple[int, Decimal, Decimal, Decimal]]:
        """Un resume par organisation : (nb creances, initial, restant, restant > 90 j).

        Une seule requete pour toutes les organisations, la ventilation etant faite par
        GROUP BY. Boucler get_stats() sur chaque organisation couterait une dizaine de
        requetes par ligne de tableau.

        Le montant au-dela de 90 jours passe par une somme conditionnelle : c'est ce qui
        evite une seconde requete pour la meme ventilation.
        """
        jours_retard = func.current_date() - Creance.date_echeance
        result = await self.db.execute(
            select(
                Creance.organisation_id,
                func.count(),
                func.coalesce(func.sum(Creance.montant_initial), 0),
                func.coalesce(func.sum(Creance.montant_restant), 0),
                func.coalesce(
                    func.sum(case((jours_retard > 90, Creance.montant_restant), else_=0)), 0
                ),
            )
            .where(Creance.statut != StatutCreance.ANNULEE)
            .group_by(Creance.organisation_id)
        )
        return {
            org: (nb, Decimal(initial), Decimal(restant), Decimal(retard_90))
            for org, nb, initial, restant, retard_90 in result.all()
        }

    async def top_debiteurs(self, organisation_id: int | None, limite: int) -> list[tuple[str, Decimal, int]]:
        """Débiteurs pesant le plus lourd dans l'encours, du plus gros au plus petit.

        Trié par restant dû et non par montant initial : ce qui compte pour arbitrer
        l'effort de recouvrement, c'est ce qu'il reste à aller chercher.
        """
        nom = func.concat(Debiteur.prenom, " ", Debiteur.nom)
        result = await self.db.execute(
            select(nom.label("nom"), func.sum(Creance.montant_restant), func.count())
            .select_from(Creance)
            .join(Debiteur, Debiteur.id == Creance.debiteur_id)
            .where(
                self._portee(organisation_id),
                Creance.statut.notin_([StatutCreance.SOLDEE, StatutCreance.ANNULEE]),
            )
            .group_by(nom)
            .order_by(func.sum(Creance.montant_restant).desc())
            .limit(limite)
        )
        return [(n, Decimal(montant), nb) for n, montant, nb in result.all()]

    async def encours_et_flux(self, organisation_id: int | None, periode_jours: int) -> tuple[Decimal, Decimal]:
        """Les deux termes du DSO : l'encours à recouvrer, et le flux confié sur la période.

        Le DSO classique rapporte l'encours au chiffre d'affaires à crédit. Un cabinet
        de recouvrement ne vend rien : l'équivalent du flux entrant est le montant des
        créances qui lui ont été confiées. C'est un proxy assumé, pas la définition
        comptable stricte — d'où le nom de la méthode, qui ne prétend pas renvoyer un DSO.

        Les créances annulées sortent des deux termes : elles ne seront jamais encaissées
        et n'ont donc leur place ni au numérateur ni au dénominateur.
        """
        vivante = Creance.statut != StatutCreance.ANNULEE

        encours = await self.db.execute(
            select(func.coalesce(func.sum(Creance.montant_restant), 0)).where(
                self._portee(organisation_id), vivante
            )
        )
        flux = await self.db.execute(
            select(func.coalesce(func.sum(Creance.montant_initial), 0)).where(
                self._portee(organisation_id),
                vivante,
                Creance.date_saisie >= func.current_date() - periode_jours,
            )
        )
        return Decimal(encours.scalar_one()), Decimal(flux.scalar_one())

    async def sum_montants(self, organisation_id: int | None) -> tuple[Decimal, Decimal]:
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(Creance.montant_initial), 0),
                func.coalesce(func.sum(Creance.montant_restant), 0),
            ).where(self._portee(organisation_id))
        )
        montant_initial, montant_restant = result.one()
        return Decimal(montant_initial), Decimal(montant_restant)
