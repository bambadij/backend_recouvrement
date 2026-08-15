from decimal import Decimal

from sqlalchemy import distinct, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.models import Client
from app.creances.models import Creance
from app.creanciers.models import Creancier
from app.debiteurs.models import Debiteur
from app.dossiers.models import Dossier, StatutDossier
from app.dossiers.schemas import DossierCreate, DossierUpdate
from app.promesses.models import Promesse
from app.relances.models import Relance


class DossierRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour la vue plateforme."""
        return Dossier.organisation_id == organisation_id if organisation_id is not None else true()

    async def create(self, data: DossierCreate, organisation_id: int) -> Dossier:
        champs = data.model_dump(exclude_none=True)
        dossier = Dossier(**champs, organisation_id=organisation_id)
        self.db.add(dossier)
        await self.db.commit()
        await self.db.refresh(dossier)
        return dossier

    async def get_by_id(self, dossier_id: int) -> Dossier | None:
        return await self.db.get(Dossier, dossier_id)

    async def get_by_reference(self, reference: str, organisation_id: int) -> Dossier | None:
        result = await self.db.execute(
            select(Dossier).where(Dossier.reference == reference, Dossier.organisation_id == organisation_id)
        )
        return result.scalar_one_or_none()

    async def lignes_creances(self, dossier_id: int) -> list[tuple]:
        """Les creances du dossier, colonnes nues, pour en tirer les faits en Python.

        Une seule requete plutot que six GROUP BY : un dossier porte des dizaines
        de factures, pas des millions, et les regroupements — statut, tranche
        d'anciennete, encours par debiteur — se calculent alors sur le meme
        instantane. Deux requetes separees pourraient se contredire.
        """
        result = await self.db.execute(
            select(
                Creance.debiteur_id,
                Creance.montant_initial,
                Creance.montant_restant,
                Creance.date_echeance,
                Creance.statut,
            ).where(Creance.dossier_id == dossier_id)
        )
        return list(result.all())

    async def compter_relances(self, dossier_id: int) -> list[tuple]:
        """Relances du dossier, groupees par canal et par statut."""
        result = await self.db.execute(
            select(Relance.type_relance, Relance.statut, func.count().label("nb"))
            .where(Relance.dossier_id == dossier_id)
            .group_by(Relance.type_relance, Relance.statut)
        )
        return list(result.all())

    async def compter_promesses(self, dossier_id: int) -> list[tuple]:
        """Engagements du dossier, groupes par statut."""
        result = await self.db.execute(
            select(Promesse.statut, func.count().label("nb"), func.coalesce(func.sum(Promesse.montant_promis), 0))
            .where(Promesse.dossier_id == dossier_id)
            .group_by(Promesse.statut)
        )
        return list(result.all())

    async def noms_debiteurs(self, dossier_id: int) -> dict[int, str]:
        result = await self.db.execute(
            select(Debiteur.id, Debiteur.prenom, Debiteur.nom, Debiteur.entreprise)
            .join(Creance, Creance.debiteur_id == Debiteur.id)
            .where(Creance.dossier_id == dossier_id)
            .distinct()
        )
        return {
            id_: (entreprise or f"{prenom} {nom}".strip())
            for id_, prenom, nom, entreprise in result.all()
        }

    async def compter_creances(self, dossier_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Creance).where(Creance.dossier_id == dossier_id)
        )
        return int(result.scalar_one())

    async def list_enrichis(
        self,
        skip: int = 0,
        limit: int = 100,
        client_id: int | None = None,
        creancier_id: int | None = None,
        statut: StatutDossier | None = None,
        organisation_id: int | None = None,
    ) -> list[tuple[Dossier, str, str | None, int, int, Decimal, Decimal]]:
        """Dossiers avec le nom des parties et les totaux de leurs creances.

        Les agregats passent par une sous-requete plutot qu'une jointure directe :
        joindre creances multiplierait les lignes de dossier et fausserait les
        comptages.
        """
        totaux = (
            select(
                Creance.dossier_id.label("dossier_id"),
                func.count().label("nb"),
                func.count(distinct(Creance.debiteur_id)).label("nb_deb"),
                func.coalesce(func.sum(Creance.montant_initial), 0).label("initial"),
                func.coalesce(func.sum(Creance.montant_restant), 0).label("restant"),
            )
            .group_by(Creance.dossier_id)
            .subquery()
        )

        query = (
            select(
                Dossier,
                Client.nom,
                Creancier.nom,
                func.coalesce(totaux.c.nb, 0),
                func.coalesce(totaux.c.nb_deb, 0),
                func.coalesce(totaux.c.initial, 0),
                func.coalesce(totaux.c.restant, 0),
            )
            .join(Client, Client.id == Dossier.client_id)
            .outerjoin(Creancier, Creancier.id == Dossier.creancier_id)
            .outerjoin(totaux, totaux.c.dossier_id == Dossier.id)
            .where(self._portee(organisation_id))
        )
        if client_id is not None:
            query = query.where(Dossier.client_id == client_id)
        if creancier_id is not None:
            query = query.where(Dossier.creancier_id == creancier_id)
        if statut is not None:
            query = query.where(Dossier.statut == statut)
        query = query.order_by(Dossier.date_reception.desc(), Dossier.id.desc()).offset(skip).limit(limit)

        result = await self.db.execute(query)
        return [
            (d, cln, crn, int(nb), int(nbd), Decimal(init), Decimal(rest))
            for d, cln, crn, nb, nbd, init, rest in result.all()
        ]

    async def update(self, dossier: Dossier, data: DossierUpdate) -> Dossier:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(dossier, field, value)
        await self.db.commit()
        await self.db.refresh(dossier)
        return dossier

    async def delete(self, dossier: Dossier) -> None:
        await self.db.delete(dossier)
        await self.db.commit()

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Dossier).where(self._portee(organisation_id))
        )
        return int(result.scalar_one())
