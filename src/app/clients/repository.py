from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.models import Client
from app.clients.schemas import ClientCreate, ClientUpdate


class ClientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour la vue plateforme."""
        return Client.organisation_id == organisation_id if organisation_id is not None else true()

    async def create(self, data: ClientCreate, organisation_id: int) -> Client:
        client = Client(**data.model_dump(), organisation_id=organisation_id)
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def get_by_id(self, client_id: int) -> Client | None:
        return await self.db.get(Client, client_id)

    async def get_by_nom(self, nom: str, organisation_id: int) -> Client | None:
        result = await self.db.execute(
            select(Client).where(Client.nom == nom, Client.organisation_id == organisation_id)
        )
        return result.scalar_one_or_none()

    async def get_interne(self, organisation_id: int) -> Client | None:
        """Le client representant l'organisation elle-meme, s'il existe."""
        result = await self.db.execute(
            select(Client)
            .where(Client.organisation_id == organisation_id, Client.is_interne.is_(True))
            .limit(1)
        )
        return result.scalars().first()

    async def create_interne(self, nom: str, organisation_id: int) -> Client:
        client = Client(nom=nom, organisation_id=organisation_id, is_interne=True)
        self.db.add(client)
        await self.db.commit()
        await self.db.refresh(client)
        return client

    async def list(
        self, skip: int = 0, limit: int = 100, search: str | None = None, organisation_id: int | None = None
    ) -> list[Client]:
        query = select(Client).where(self._portee(organisation_id))
        if search:
            query = query.where(Client.nom.ilike(f"%{search}%"))
        # Le client interne en tete : c'est le plus utilise au quotidien.
        query = query.order_by(Client.is_interne.desc(), Client.nom).offset(skip).limit(limit)
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

    async def compter_dossiers(self, client_id: int) -> int:
        from app.dossiers.models import Dossier

        result = await self.db.execute(
            select(func.count()).select_from(Dossier).where(Dossier.client_id == client_id)
        )
        return int(result.scalar_one())

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Client).where(self._portee(organisation_id))
        )
        return int(result.scalar_one())
