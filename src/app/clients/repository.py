from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.models import Client
from app.clients.schemas import ClientCreate, ClientUpdate


class ClientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: ClientCreate, organisation_id: int) -> Client:
        client = Client(**data.model_dump(), organisation_id=organisation_id)
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def get_by_id(self, client_id: int) -> Client | None:
        return await self.db.get(Client, client_id)

    async def get_by_email(self, email: str, organisation_id: int) -> Client | None:
        result = await self.db.execute(
            select(Client).where(Client.email == email, Client.organisation_id == organisation_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self, skip: int = 0, limit: int = 100, search: str | None = None, organisation_id: int | None = None
    ) -> list[Client]:
        query = select(Client)
        if organisation_id is not None:
            query = query.where(Client.organisation_id == organisation_id)
        if search:
            like = f"%{search}%"
            query = query.where((Client.nom.ilike(like)) | (Client.prenom.ilike(like)) | (Client.entreprise.ilike(like)))
        query = query.order_by(Client.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, client: Client, data: ClientUpdate) -> Client:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(client, field, value)
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def delete(self, client: Client) -> None:
        await self.db.delete(client)
        await self.db.commit()

    async def count(self, organisation_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Client).where(Client.organisation_id == organisation_id)
        )
        return result.scalar_one()
