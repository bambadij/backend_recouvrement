from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.organisations.models import Organisation
from app.organisations.schemas import OrganisationCreate, OrganisationUpdate


class OrganisationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: OrganisationCreate) -> Organisation:
        organisation = Organisation(**data.model_dump())
        self.db.add(organisation)
        await self.db.commit()
        await self.db.refresh(organisation)
        return organisation

    async def get_by_id(self, organisation_id: int) -> Organisation | None:
        return await self.db.get(Organisation, organisation_id)

    async def get_by_nom(self, nom: str) -> Organisation | None:
        result = await self.db.execute(select(Organisation).where(Organisation.nom == nom))
        return result.scalar_one_or_none()

    async def list(self, skip: int = 0, limit: int = 100) -> list[Organisation]:
        query = select(Organisation).order_by(Organisation.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, organisation: Organisation, data: OrganisationUpdate) -> Organisation:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(organisation, field, value)
        await self.db.commit()
        await self.db.refresh(organisation)
        return organisation

    async def delete(self, organisation: Organisation) -> None:
        await self.db.delete(organisation)
        await self.db.commit()
