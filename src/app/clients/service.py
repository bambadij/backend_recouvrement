from app.clients.models import Client
from app.clients.repository import ClientRepository
from app.clients.schemas import ClientCreate, ClientUpdate
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
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
        if await self.repository.get_by_nom(data.nom, organisation_id):
            raise ConflictException(f"Un client nomme « {data.nom} » existe deja")
        return await self.repository.create(data, organisation_id)

    async def get_client(self, client_id: int) -> Client:
        client = await self.repository.get_by_id(client_id)
        if client is None or (
            self.current_user.organisation_id is not None
            and client.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Client {client_id} introuvable")
        return client

    async def get_ou_creer_interne(self, organisation_id: int, nom: str) -> Client:
        """Le client representant l'organisation elle-meme, cree au besoin.

        Sert au cas courant de l'organisation qui recouvre ses propres impayes :
        elle est son propre client, sans donneur d'ordre tiers.
        """
        existant = await self.repository.get_interne(organisation_id)
        if existant is not None:
            return existant
        return await self.repository.create_interne(nom, organisation_id)

    async def list_clients(self, skip: int = 0, limit: int = 100, search: str | None = None) -> list[Client]:
        return await self.repository.list(
            skip=skip, limit=limit, search=search, organisation_id=self.current_user.organisation_id
        )

    async def update_client(self, client_id: int, data: ClientUpdate) -> Client:
        client = await self.get_client(client_id)
        self._writable_organisation_id()
        if data.nom and data.nom != client.nom:
            if await self.repository.get_by_nom(data.nom, client.organisation_id):
                raise ConflictException(f"Un client nomme « {data.nom} » existe deja")
        return await self.repository.update(client, data)

    async def delete_client(self, client_id: int) -> None:
        client = await self.get_client(client_id)
        self._writable_organisation_id()
        # Un client qui a confie des dossiers ne disparait pas : ses dossiers
        # perdraient leur donneur d'ordre, et la FK est en RESTRICT de toute facon.
        if await self.repository.compter_dossiers(client.id) > 0:
            raise BadRequestException(
                "Ce client a des dossiers en cours : supprimez-les d'abord ou archivez le client"
            )
        await self.repository.delete(client)
