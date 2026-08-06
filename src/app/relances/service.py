from app.core.exceptions import ForbiddenException, NotFoundException
from app.debiteurs.service import DebiteurService
from app.dossiers.service import DossierService
from app.relances.models import Relance, StatutRelance
from app.relances.repository import RelanceRepository
from app.relances.schemas import RelanceCreate, RelanceUpdate
from app.users.models import User


class RelanceService:
    def __init__(
        self,
        repository: RelanceRepository,
        dossier_service: DossierService,
        debiteur_service: DebiteurService,
        current_user: User,
    ) -> None:
        self.repository = repository
        self.dossier_service = dossier_service
        self.debiteur_service = debiteur_service
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_relance(self, data: RelanceCreate) -> Relance:
        organisation_id = self._writable_organisation_id()
        await self.dossier_service.get_dossier(data.dossier_id)  # 404 si dossier d'une autre organisation
        await self.debiteur_service.get_debiteur(data.debiteur_id)
        agent = f"{self.current_user.prenom} {self.current_user.nom}".strip() or None
        return await self.repository.create(data, organisation_id, cree_par_nom=agent)

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
        dossier_id: int | None = None,
        debiteur_id: int | None = None,
        statut: StatutRelance | None = None,
        avec_resultat: bool | None = None,
    ) -> list[Relance]:
        return await self.repository.list(
            skip=skip,
            limit=limit,
            dossier_id=dossier_id,
            debiteur_id=debiteur_id,
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
