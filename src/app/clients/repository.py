from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.models import Client
from app.clients.schemas import ClientCreate, ClientUpdate


class ClientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour une vue plateforme.

        organisation_id None signifie « toutes les organisations » : le SUPER_ADMIN
        consulte alors le parc entier. Renvoyer true() plutot que d'omettre la clause
        garde la forme des requetes identique dans les deux cas.
        """
        return Client.organisation_id == organisation_id if organisation_id is not None else true()


    async def create(self, data: ClientCreate, organisation_id: int | None) -> Client:
        client = Client(**data.model_dump(), organisation_id=organisation_id)
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def get_by_id(self, client_id: int) -> Client | None:
        return await self.db.get(Client, client_id)

    async def get_by_email(self, email: str, organisation_id: int | None) -> Client | None:
        result = await self.db.execute(
            select(Client).where(Client.email == email, self._portee(organisation_id))
        )
        return result.scalar_one_or_none()

    async def get_by_telephone(self, telephone: str, organisation_id: int | None) -> Client | None:
        result = await self.db.execute(
            select(Client)
            .where(Client.telephone == telephone, self._portee(organisation_id))
            .limit(1)
        )
        return result.scalars().first()

    async def list(
        self, skip: int = 0, limit: int = 100, search: str | None = None, organisation_id: int | None = None
    ) -> list[Client]:
        query = select(Client)
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
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

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Client).where(self._portee(organisation_id))
        )
        return result.scalar_one()
