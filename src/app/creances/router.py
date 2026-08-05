from fastapi import APIRouter, Query, status

from app.creances.dependencies import CreanceServiceDep
from app.creances.models import StatutCreance
from app.creances.schemas import CreanceCreate, CreanceRead, CreanceUpdate

router = APIRouter(prefix="/creances", tags=["creances"])


@router.post("", response_model=CreanceRead, status_code=status.HTTP_201_CREATED)
async def create_creance(data: CreanceCreate, service: CreanceServiceDep) -> CreanceRead:
    creance = await service.create_creance(data)
    return CreanceRead.model_validate(creance)


@router.get("", response_model=list[CreanceRead])
async def list_creances(
    service: CreanceServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    debiteur_id: int | None = None,
    statut: StatutCreance | None = None,
) -> list[CreanceRead]:
    creances = await service.list_creances(skip=skip, limit=limit, debiteur_id=debiteur_id, statut=statut)
    return [CreanceRead.model_validate(c) for c in creances]


@router.get("/{creance_id}", response_model=CreanceRead)
async def get_creance(creance_id: int, service: CreanceServiceDep) -> CreanceRead:
    creance = await service.get_creance(creance_id)
    return CreanceRead.model_validate(creance)


@router.patch("/{creance_id}", response_model=CreanceRead)
async def update_creance(creance_id: int, data: CreanceUpdate, service: CreanceServiceDep) -> CreanceRead:
    creance = await service.update_creance(creance_id, data)
    return CreanceRead.model_validate(creance)


@router.delete("/{creance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creance(creance_id: int, service: CreanceServiceDep) -> None:
    await service.delete_creance(creance_id)
