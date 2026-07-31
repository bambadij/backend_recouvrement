from __future__ import annotations

from decimal import Decimal

from sqlalchemy.dialects.postgresql import INTERVAL
from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.creances.models import Creance
from app.paiements.models import Paiement
from app.paiements.schemas import PaiementCreate


class PaiementRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour une vue plateforme.

        organisation_id None signifie « toutes les organisations » : le SUPER_ADMIN
        consulte alors le parc entier. Renvoyer true() plutot que d'omettre la clause
        garde la forme des requetes identique dans les deux cas.
        """
        return Paiement.organisation_id == organisation_id if organisation_id is not None else true()


    async def create(
        self, data: PaiementCreate, organisation_id: int | None, saisi_par_nom: str | None = None
    ) -> Paiement:
        paiement = Paiement(**data.model_dump(), organisation_id=organisation_id, saisi_par_nom=saisi_par_nom)
        self.db.add(paiement)
        await self.db.commit()
        await self.db.refresh(paiement)
        return paiement

    async def get_by_id(self, paiement_id: int) -> Paiement | None:
        return await self.db.get(Paiement, paiement_id)

    async def list(
        self, skip: int = 0, limit: int = 100, creance_id: int | None = None, organisation_id: int | None = None
    ) -> list[Paiement]:
        query = select(Paiement)
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
        if creance_id is not None:
            query = query.where(Paiement.creance_id == creance_id)
        query = query.order_by(Paiement.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def recouvrement_par_organisation_et_mois(
        self, nb_mois: int
    ) -> list[tuple[int, str, Decimal]]:
        """Montants encaisses, ventiles par organisation et par mois de paiement.

        Une seule requete pour tout le parc : la comparaison entre organisations se
        fait par GROUP BY, pas par une boucle d'appels.

        La fenetre couvre nb_mois mois calendaires en incluant le mois courant, d'ou
        le nb_mois - 1 : demander 6 mois en juillet part de fevrier.
        """
        mois = func.to_char(Paiement.date_paiement, "YYYY-MM")
        debut = func.date_trunc("month", func.current_date()) - func.cast(
            func.concat(nb_mois - 1, " months"), INTERVAL
        )
        result = await self.db.execute(
            select(Paiement.organisation_id, mois.label("mois"), func.coalesce(func.sum(Paiement.montant), 0))
            .where(Paiement.date_paiement >= debut)
            .group_by(Paiement.organisation_id, mois)
            .order_by(mois)
        )
        return [(org, m, Decimal(montant)) for org, m, montant in result.all()]

    async def encaissements_par_utilisateur(
        self, organisation_id: int | None, periode_jours: int
    ) -> list[tuple[str, Decimal, int]]:
        """Montants encaissés par utilisateur ayant saisi le versement, sur la période.

        Mesure d'activité de saisie, PAS de performance de recouvrement : `saisi_par_nom`
        dit qui a enregistre l'encaissement, pas qui a obtenu le paiement. Le modele ne
        porte aucune affectation d'une creance a un agent, donc rien de plus fin n'est
        calculable aujourd'hui — le libelle cote interface doit rester exact.
        """
        nom = func.coalesce(Paiement.saisi_par_nom, "Non renseigné")
        result = await self.db.execute(
            select(nom.label("nom"), func.sum(Paiement.montant), func.count())
            .where(
                self._portee(organisation_id),
                Paiement.date_paiement >= func.current_date() - periode_jours,
            )
            .group_by(nom)
            .order_by(func.sum(Paiement.montant).desc())
        )
        return [(n, Decimal(montant), nb) for n, montant, nb in result.all()]

    async def delai_moyen_encaissement(self, organisation_id: int | None, periode_jours: int) -> int | None:
        """Jours écoulés entre l'échéance et l'encaissement, pondérés par les montants.

        Contrairement au DSO, qui estime à partir d'un encours, c'est une mesure : on
        ne regarde que de l'argent réellement rentré. La pondération par le montant
        évite qu'un règlement de 5 000 F pèse autant qu'un de 5 000 000 F.

        Renvoie None si aucun encaissement sur la période — un zéro laisserait croire
        que tout est réglé le jour de l'échéance.
        """
        jours = Paiement.date_paiement - Creance.date_echeance
        result = await self.db.execute(
            select(
                func.sum(Paiement.montant * jours) / func.nullif(func.sum(Paiement.montant), 0)
            )
            .select_from(Paiement)
            .join(Creance, Creance.id == Paiement.creance_id)
            .where(
                self._portee(organisation_id),
                Paiement.date_paiement >= func.current_date() - periode_jours,
            )
        )
        valeur = result.scalar_one_or_none()
        return int(round(float(valeur))) if valeur is not None else None

    async def stats(self, organisation_id: int | None) -> tuple[int, Decimal]:
        result = await self.db.execute(
            select(func.count(), func.coalesce(func.sum(Paiement.montant), 0)).where(
                self._portee(organisation_id)
            )
        )
        count, total = result.one()
        return count, Decimal(total)
