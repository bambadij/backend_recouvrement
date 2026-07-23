from app.core.exceptions import ConflictException, NotFoundException
from app.organisations.models import Organisation
from app.organisations.repository import OrganisationRepository
from app.organisations.schemas import OrganisationCreate, OrganisationUpdate


class OrganisationService:
    def __init__(self, repository: OrganisationRepository) -> None:
        self.repository = repository

    async def create_organisation(self, data: OrganisationCreate) -> Organisation:
        if await self.repository.get_by_nom(data.nom):
            raise ConflictException(f"Une organisation nommee {data.nom} existe deja")
        return await self.repository.create(data)

    async def get_organisation(self, organisation_id: int) -> Organisation:
        organisation = await self.repository.get_by_id(organisation_id)
        if organisation is None:
            raise NotFoundException(f"Organisation {organisation_id} introuvable")
        return organisation

    async def list_organisations(self, skip: int = 0, limit: int = 100) -> list[Organisation]:
        return await self.repository.list(skip=skip, limit=limit)

    async def update_organisation(self, organisation_id: int, data: OrganisationUpdate) -> Organisation:
        organisation = await self.get_organisation(organisation_id)
        return await self.repository.update(organisation, data)

    async def delete_organisation(self, organisation_id: int) -> None:
        organisation = await self.get_organisation(organisation_id)
        await self.repository.delete(organisation)
