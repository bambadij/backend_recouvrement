from fastapi import APIRouter, Query, status

from app.core.exceptions import NotFoundException
from app.organisations.dependencies import OrganisationServiceDep, OrganisationStatsServiceDep
from app.organisations.schemas import OrganisationCreate, OrganisationRead, OrganisationStats, OrganisationUpdate
from app.users.dependencies import CurrentSuperAdminDep, CurrentUserDep

router = APIRouter(prefix="/organisations", tags=["organisations"])


@router.post("", response_model=OrganisationRead, status_code=status.HTTP_201_CREATED)
async def create_organisation(
    data: OrganisationCreate, service: OrganisationServiceDep, _super_admin: CurrentSuperAdminDep
) -> OrganisationRead:
    organisation = await service.create_organisation(data)
    return OrganisationRead.model_validate(organisation)


@router.get("", response_model=list[OrganisationRead])
async def list_organisations(
    service: OrganisationServiceDep,
    _super_admin: CurrentSuperAdminDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[OrganisationRead]:
    organisations = await service.list_organisations(skip=skip, limit=limit)
    return [OrganisationRead.model_validate(o) for o in organisations]


@router.get("/me", response_model=OrganisationRead)
async def get_my_organisation(current_user: CurrentUserDep, service: OrganisationServiceDep) -> OrganisationRead:
    if current_user.organisation_id is None:
        raise NotFoundException("Le SUPER_ADMIN n'appartient a aucune organisation")
    organisation = await service.get_organisation(current_user.organisation_id)
    return OrganisationRead.model_validate(organisation)


@router.get("/me/stats", response_model=OrganisationStats)
async def get_my_organisation_stats(
    current_user: CurrentUserDep, service: OrganisationStatsServiceDep
) -> OrganisationStats:
    if current_user.organisation_id is None:
        raise NotFoundException("Le SUPER_ADMIN n'appartient a aucune organisation")
    return await service.get_stats(current_user.organisation_id)


@router.get("/{organisation_id}", response_model=OrganisationRead)
async def get_organisation(
    organisation_id: int, service: OrganisationServiceDep, _super_admin: CurrentSuperAdminDep
) -> OrganisationRead:
    organisation = await service.get_organisation(organisation_id)
    return OrganisationRead.model_validate(organisation)


@router.get("/{organisation_id}/stats", response_model=OrganisationStats)
async def get_organisation_stats(
    organisation_id: int, service: OrganisationStatsServiceDep, _super_admin: CurrentSuperAdminDep
) -> OrganisationStats:
    return await service.get_stats(organisation_id)


@router.patch("/{organisation_id}", response_model=OrganisationRead)
async def update_organisation(
    organisation_id: int,
    data: OrganisationUpdate,
    service: OrganisationServiceDep,
    _super_admin: CurrentSuperAdminDep,
) -> OrganisationRead:
    organisation = await service.update_organisation(organisation_id, data)
    return OrganisationRead.model_validate(organisation)


@router.delete("/{organisation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organisation(
    organisation_id: int, service: OrganisationServiceDep, _super_admin: CurrentSuperAdminDep
) -> None:
    await service.delete_organisation(organisation_id)
