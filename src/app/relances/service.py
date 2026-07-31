from app.core.exceptions import ForbiddenException, NotFoundException
from app.creances.service import CreanceService
from app.relances.models import Relance, StatutRelance
from app.relances.repository import RelanceRepository
from app.relances.schemas import RelanceCreate, RelanceUpdate
from app.users.models import User


class RelanceService:
    def __init__(self, repository: RelanceRepository, creance_service: CreanceService, current_user: User) -> None:
        self.repository = repository
        self.creance_service = creance_service
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_relance(self, data: RelanceCreate) -> Relance:
        organisation_id = self._writable_organisation_id()
        await self.creance_service.get_creance(data.creance_id)  # 404 si creance d'une autre organisation
        return await self.repository.create(data, organisation_id)

    async def get_relance(self, relance_id: int) -> Relance:
        relance = await self.repository.get_by_id(relance_id)
        if relance is None or (
            self.current_user.organisation_id is not None
            and relance.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Relance {relance_id} introuvable")
        return relance

    async def list_relances(
        self,
        skip: int = 0,
        limit: int = 100,
        creance_id: int | None = None,
        statut: StatutRelance | None = None,
        avec_resultat: bool | None = None,
    ) -> list[Relance]:
        return await self.repository.list(
            skip=skip,
            limit=limit,
            creance_id=creance_id,
            organisation_id=self.current_user.organisation_id,
            statut=statut,
            avec_resultat=avec_resultat,
        )

    async def update_relance(self, relance_id: int, data: RelanceUpdate) -> Relance:
        relance = await self.get_relance(relance_id)
        self._writable_organisation_id()
        return await self.repository.update(relance, data)

    async def delete_relance(self, relance_id: int) -> None:
        relance = await self.get_relance(relance_id)
        self._writable_organisation_id()
        await self.repository.delete(relance)
