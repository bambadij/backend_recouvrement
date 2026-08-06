from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.creanciers.models import Creancier
from app.creanciers.repository import CreancierRepository
from app.creanciers.schemas import CreancierCreate, CreancierUpdate
from app.users.models import User


class CreancierService:
    def __init__(self, repository: CreancierRepository, current_user: User) -> None:
        self.repository = repository
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_creancier(self, data: CreancierCreate) -> Creancier:
        organisation_id = self._writable_organisation_id()
        if await self.repository.get_by_nom(data.nom, organisation_id):
            raise ConflictException(f"Un creancier nomme « {data.nom} » existe deja")
        return await self.repository.create(data, organisation_id)

    async def get_creancier(self, creancier_id: int) -> Creancier:
        creancier = await self.repository.get_by_id(creancier_id)
        if creancier is None or (
            self.current_user.organisation_id is not None
            and creancier.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Creancier {creancier_id} introuvable")
        return creancier

    async def list_creanciers(self, skip: int = 0, limit: int = 100, search: str | None = None) -> list[Creancier]:
        return await self.repository.list(
            skip=skip, limit=limit, search=search, organisation_id=self.current_user.organisation_id
        )

    async def update_creancier(self, creancier_id: int, data: CreancierUpdate) -> Creancier:
        creancier = await self.get_creancier(creancier_id)
        self._writable_organisation_id()
        if data.nom and data.nom != creancier.nom:
            if await self.repository.get_by_nom(data.nom, creancier.organisation_id):
                raise ConflictException(f"Un creancier nomme « {data.nom} » existe deja")
        return await self.repository.update(creancier, data)

    async def delete_creancier(self, creancier_id: int) -> None:
        creancier = await self.get_creancier(creancier_id)
        self._writable_organisation_id()
        if await self.repository.compter_dossiers(creancier.id) > 0:
            raise BadRequestException("Ce creancier est rattache a des dossiers : supprimez-les d'abord")
        await self.repository.delete(creancier)
