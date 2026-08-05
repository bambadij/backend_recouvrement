from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.debiteurs.models import Debiteur
from app.debiteurs.repository import DebiteurRepository
from app.debiteurs.schemas import DebiteurCreate, DebiteurUpdate
from app.users.models import User


class DebiteurService:
    def __init__(self, repository: DebiteurRepository, current_user: User) -> None:
        self.repository = repository
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_debiteur(self, data: DebiteurCreate) -> Debiteur:
        organisation_id = self._writable_organisation_id()
        if data.email and await self.repository.get_by_email(data.email, organisation_id):
            raise ConflictException(f"Un debiteur avec l'email {data.email} existe deja")
        return await self.repository.create(data, organisation_id)

    async def get_debiteur(self, debiteur_id: int) -> Debiteur:
        debiteur = await self.repository.get_by_id(debiteur_id)
        if debiteur is None or (
            self.current_user.organisation_id is not None
            and debiteur.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Debiteur {debiteur_id} introuvable")
        return debiteur

    async def list_debiteurs(self, skip: int = 0, limit: int = 100, search: str | None = None) -> list[Debiteur]:
        return await self.repository.list(
            skip=skip, limit=limit, search=search, organisation_id=self.current_user.organisation_id
        )

    async def update_debiteur(self, debiteur_id: int, data: DebiteurUpdate) -> Debiteur:
        debiteur = await self.get_debiteur(debiteur_id)
        self._writable_organisation_id()
        if data.email and data.email != debiteur.email:
            existing = await self.repository.get_by_email(data.email, debiteur.organisation_id)
            if existing is not None:
                raise ConflictException(f"Un debiteur avec l'email {data.email} existe deja")
        return await self.repository.update(debiteur, data)

    async def delete_debiteur(self, debiteur_id: int) -> None:
        debiteur = await self.get_debiteur(debiteur_id)
        self._writable_organisation_id()
        await self.repository.delete(debiteur)
