from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.relances.models import Relance
from app.relances.schemas import RelanceCreate, RelanceUpdate


class RelanceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: RelanceCreate, organisation_id: int) -> Relance:
        relance = Relance(**data.model_dump(), organisation_id=organisation_id)
        self.db.add(relance)
        await self.db.commit()
        await self.db.refresh(relance)
        return relance

    async def get_by_id(self, relance_id: int) -> Relance | None:
        return await self.db.get(Relance, relance_id)

    async def list(
        self, skip: int = 0, limit: int = 100, creance_id: int | None = None, organisation_id: int | None = None
    ) -> list[Relance]:
        query = select(Relance)
        if organisation_id is not None:
            query = query.where(Relance.organisation_id == organisation_id)
        if creance_id is not None:
            query = query.where(Relance.creance_id == creance_id)
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

    async def count(self, organisation_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Relance).where(Relance.organisation_id == organisation_id)
        )
        return result.scalar_one()
