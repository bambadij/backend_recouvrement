from fastapi import APIRouter, Query, status

from app.paiements.dependencies import PaiementServiceDep
from app.paiements.schemas import PaiementCreate, PaiementRead

router = APIRouter(prefix="/paiements", tags=["paiements"])


@router.post("", response_model=PaiementRead, status_code=status.HTTP_201_CREATED)
async def create_paiement(data: PaiementCreate, service: PaiementServiceDep) -> PaiementRead:
    paiement = await service.create_paiement(data)
    return PaiementRead.model_validate(paiement)


@router.get("", response_model=list[PaiementRead])
async def list_paiements(
    service: PaiementServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    creance_id: int | None = None,
) -> list[PaiementRead]:
    paiements = await service.list_paiements(skip=skip, limit=limit, creance_id=creance_id)
    return [PaiementRead.model_validate(p) for p in paiements]


@router.get("/{paiement_id}", response_model=PaiementRead)
async def get_paiement(paiement_id: int, service: PaiementServiceDep) -> PaiementRead:
    paiement = await service.get_paiement(paiement_id)
    return PaiementRead.model_validate(paiement)
