from app.clients.models import Client
from app.clients.repository import ClientRepository
from app.clients.schemas import ClientCreate, ClientUpdate
from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.users.models import User


class ClientService:
    def __init__(self, repository: ClientRepository, current_user: User) -> None:
        self.repository = repository
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_client(self, data: ClientCreate) -> Client:
        organisation_id = self._writable_organisation_id()
        if data.email and await self.repository.get_by_email(data.email, organisation_id):
            raise ConflictException(f"Un client avec l'email {data.email} existe deja")
        return await self.repository.create(data, organisation_id)

    async def get_client(self, client_id: int) -> Client:
        client = await self.repository.get_by_id(client_id)
        if client is None or (
            self.current_user.organisation_id is not None
            and client.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Client {client_id} introuvable")
        return client

    async def list_clients(self, skip: int = 0, limit: int = 100, search: str | None = None) -> list[Client]:
        return await self.repository.list(
            skip=skip, limit=limit, search=search, organisation_id=self.current_user.organisation_id
        )

    async def update_client(self, client_id: int, data: ClientUpdate) -> Client:
        client = await self.get_client(client_id)
        self._writable_organisation_id()
        if data.email and data.email != client.email:
            existing = await self.repository.get_by_email(data.email, client.organisation_id)
            if existing is not None:
                raise ConflictException(f"Un client avec l'email {data.email} existe deja")
        return await self.repository.update(client, data)

    async def delete_client(self, client_id: int) -> None:
        client = await self.get_client(client_id)
        self._writable_organisation_id()
        await self.repository.delete(client)
