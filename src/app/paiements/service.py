from app.core.exceptions import NotFoundException
from app.creances.service import CreanceService
from app.paiements.models import Paiement
from app.paiements.repository import PaiementRepository
from app.paiements.schemas import PaiementCreate
from app.users.models import User


class PaiementService:
    def __init__(self, repository: PaiementRepository, creance_service: CreanceService, current_user: User) -> None:
        self.repository = repository
        self.creance_service = creance_service
        self.current_user = current_user

    async def create_paiement(self, data: PaiementCreate) -> Paiement:
        await self.creance_service.enregistrer_paiement(data.creance_id, data.montant)
        # enregistrer_paiement a deja verifie que current_user appartient a une organisation
        return await self.repository.create(data, self.current_user.organisation_id)  # type: ignore[arg-type]

    async def get_paiement(self, paiement_id: int) -> Paiement:
        paiement = await self.repository.get_by_id(paiement_id)
        if paiement is None or (
            self.current_user.organisation_id is not None
            and paiement.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Paiement {paiement_id} introuvable")
        return paiement

    async def list_paiements(self, skip: int = 0, limit: int = 100, creance_id: int | None = None) -> list[Paiement]:
        return await self.repository.list(
            skip=skip, limit=limit, creance_id=creance_id, organisation_id=self.current_user.organisation_id
        )
