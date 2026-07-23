from decimal import Decimal

from app.clients.service import ClientService
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.creances.models import Creance, StatutCreance
from app.creances.repository import CreanceRepository
from app.creances.schemas import CreanceCreate, CreanceUpdate
from app.users.models import User


class CreanceService:
    def __init__(self, repository: CreanceRepository, client_service: ClientService, current_user: User) -> None:
        self.repository = repository
        self.client_service = client_service
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_creance(self, data: CreanceCreate) -> Creance:
        organisation_id = self._writable_organisation_id()
        await self.client_service.get_client(data.client_id)  # 404 si client d'une autre organisation
        if await self.repository.get_by_reference(data.reference, organisation_id):
            raise ConflictException(f"La reference {data.reference} existe deja")
        return await self.repository.create(data, organisation_id)

    async def get_creance(self, creance_id: int) -> Creance:
        creance = await self.repository.get_by_id(creance_id)
        if creance is None or (
            self.current_user.organisation_id is not None
            and creance.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Creance {creance_id} introuvable")
        return creance

    async def list_creances(
        self, skip: int = 0, limit: int = 100, client_id: int | None = None, statut: StatutCreance | None = None
    ) -> list[Creance]:
        return await self.repository.list(
            skip=skip,
            limit=limit,
            client_id=client_id,
            statut=statut,
            organisation_id=self.current_user.organisation_id,
        )

    async def update_creance(self, creance_id: int, data: CreanceUpdate) -> Creance:
        creance = await self.get_creance(creance_id)
        self._writable_organisation_id()
        return await self.repository.update(creance, data)

    async def delete_creance(self, creance_id: int) -> None:
        creance = await self.get_creance(creance_id)
        self._writable_organisation_id()
        await self.repository.delete(creance)

    async def enregistrer_paiement(self, creance_id: int, montant: Decimal) -> Creance:
        """Decremente montant_restant et passe la creance en SOLDEE si elle atteint zero."""
        creance = await self.get_creance(creance_id)
        self._writable_organisation_id()
        if creance.statut == StatutCreance.SOLDEE:
            raise BadRequestException("Cette creance est deja soldee")
        if montant <= 0:
            raise BadRequestException("Le montant du paiement doit etre positif")
        if montant > creance.montant_restant:
            raise BadRequestException("Le montant du paiement depasse le montant restant du")
        return await self.repository.appliquer_paiement(creance, montant)
