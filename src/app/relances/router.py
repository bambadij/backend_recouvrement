from fastapi import APIRouter, Query, status

from app.relances.dependencies import RelanceServiceDep
from app.relances.models import StatutRelance
from app.relances.schemas import RelanceCreate, RelanceRead, RelanceUpdate

router = APIRouter(prefix="/relances", tags=["relances"])


@router.post("", response_model=RelanceRead, status_code=status.HTTP_201_CREATED)
async def create_relance(data: RelanceCreate, service: RelanceServiceDep) -> RelanceRead:
    relance = await service.create_relance(data)
    return RelanceRead.model_validate(relance)


@router.get("", response_model=list[RelanceRead])
async def list_relances(
    service: RelanceServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    creance_id: int | None = None,
    statut: StatutRelance | None = None,
    avec_resultat: bool | None = Query(
        None, description="true : uniquement les relances portant un resultat (engagement obtenu)"
    ),
) -> list[RelanceRead]:
    relances = await service.list_relances(
        skip=skip, limit=limit, creance_id=creance_id, statut=statut, avec_resultat=avec_resultat
    )
    return [RelanceRead.model_validate(r) for r in relances]


@router.get("/{relance_id}", response_model=RelanceRead)
async def get_relance(relance_id: int, service: RelanceServiceDep) -> RelanceRead:
    relance = await service.get_relance(relance_id)
    return RelanceRead.model_validate(relance)


@router.patch("/{relance_id}", response_model=RelanceRead)
async def update_relance(relance_id: int, data: RelanceUpdate, service: RelanceServiceDep) -> RelanceRead:
    relance = await service.update_relance(relance_id, data)
    return RelanceRead.model_validate(relance)


@router.delete("/{relance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relance(relance_id: int, service: RelanceServiceDep) -> None:
    await service.delete_relance(relance_id)
