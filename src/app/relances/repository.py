from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.relances.models import Relance, StatutRelance
from app.relances.schemas import RelanceCreate, RelanceUpdate


class RelanceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour une vue plateforme.

        organisation_id None signifie « toutes les organisations » : le SUPER_ADMIN
        consulte alors le parc entier. Renvoyer true() plutot que d'omettre la clause
        garde la forme des requetes identique dans les deux cas.
        """
        return Relance.organisation_id == organisation_id if organisation_id is not None else true()


    async def create(self, data: RelanceCreate, organisation_id: int | None) -> Relance:
        relance = Relance(**data.model_dump(), organisation_id=organisation_id)
        self.db.add(relance)
        await self.db.commit()
        await self.db.refresh(relance)
        return relance

    async def get_by_id(self, relance_id: int) -> Relance | None:
        return await self.db.get(Relance, relance_id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        creance_id: int | None = None,
        organisation_id: int | None = None,
        statut: StatutRelance | None = None,
        avec_resultat: bool | None = None,
    ) -> list[Relance]:
        query = select(Relance)
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
        if creance_id is not None:
            query = query.where(Relance.creance_id == creance_id)
        if statut is not None:
            query = query.where(Relance.statut == statut)
        if avec_resultat is not None:
            # Un resultat renseigne = un engagement obtenu du debiteur, a recontroler.
            # La chaine vide compte comme absent : sinon un champ efface passerait pour
            # une promesse.
            renseigne = Relance.resultat.isnot(None) & (Relance.resultat != "")
            query = query.where(renseigne if avec_resultat else ~renseigne)
        query = query.order_by(Relance.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, relance: Relance, data: RelanceUpdate) -> Relance:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(relance, field, value)
        await self.db.commit()
        await self.db.refresh(relance)
        return relance

    async def delete(self, relance: Relance) -> None:
        await self.db.delete(relance)
        await self.db.commit()

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Relance).where(self._portee(organisation_id))
        )
        return result.scalar_one()
