from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.creanciers.models import Creancier
from app.creanciers.schemas import CreancierCreate, CreancierUpdate


class CreancierRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour la vue plateforme."""
        return Creancier.organisation_id == organisation_id if organisation_id is not None else true()

    async def create(self, data: CreancierCreate, organisation_id: int) -> Creancier:
        creancier = Creancier(**data.model_dump(), organisation_id=organisation_id)
        self.db.add(creancier)
        await self.db.commit()
        await self.db.refresh(creancier)
        return creancier

    async def get_by_id(self, creancier_id: int) -> Creancier | None:
        return await self.db.get(Creancier, creancier_id)

    async def get_by_nom(self, nom: str, organisation_id: int) -> Creancier | None:
        result = await self.db.execute(
            select(Creancier).where(Creancier.nom == nom, Creancier.organisation_id == organisation_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self, skip: int = 0, limit: int = 100, search: str | None = None, organisation_id: int | None = None
    ) -> list[Creancier]:
        query = select(Creancier).where(self._portee(organisation_id))
        if search:
            query = query.where(Creancier.nom.ilike(f"%{search}%"))
        query = query.order_by(Creancier.nom).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, creancier: Creancier, data: CreancierUpdate) -> Creancier:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(creancier, field, value)
        await self.db.commit()
        await self.db.refresh(creancier)
        return creancier

    async def delete(self, creancier: Creancier) -> None:
        await self.db.delete(creancier)
        await self.db.commit()

    async def compter_dossiers(self, creancier_id: int) -> int:
        from app.dossiers.models import Dossier

        result = await self.db.execute(
            select(func.count()).select_from(Dossier).where(Dossier.creancier_id == creancier_id)
        )
        return int(result.scalar_one())

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Creancier).where(self._portee(organisation_id))
        )
        return int(result.scalar_one())
