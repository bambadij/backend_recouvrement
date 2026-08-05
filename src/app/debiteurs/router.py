from fastapi import APIRouter, Query, status

from app.debiteurs.dependencies import DebiteurServiceDep
from app.debiteurs.schemas import DebiteurCreate, DebiteurRead, DebiteurUpdate

router = APIRouter(prefix="/debiteurs", tags=["debiteurs"])


@router.post("", response_model=DebiteurRead, status_code=status.HTTP_201_CREATED)
async def create_debiteur(data: DebiteurCreate, service: DebiteurServiceDep) -> DebiteurRead:
    debiteur = await service.create_debiteur(data)
    return DebiteurRead.model_validate(debiteur)


@router.get("", response_model=list[DebiteurRead])
async def list_debiteurs(
    service: DebiteurServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
) -> list[DebiteurRead]:
    debiteurs = await service.list_debiteurs(skip=skip, limit=limit, search=search)
    return [DebiteurRead.model_validate(d) for d in debiteurs]


@router.get("/{debiteur_id}", response_model=DebiteurRead)
async def get_debiteur(debiteur_id: int, service: DebiteurServiceDep) -> DebiteurRead:
    debiteur = await service.get_debiteur(debiteur_id)
    return DebiteurRead.model_validate(debiteur)


@router.patch("/{debiteur_id}", response_model=DebiteurRead)
async def update_debiteur(debiteur_id: int, data: DebiteurUpdate, service: DebiteurServiceDep) -> DebiteurRead:
    debiteur = await service.update_debiteur(debiteur_id, data)
    return DebiteurRead.model_validate(debiteur)


@router.delete("/{debiteur_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_debiteur(debiteur_id: int, service: DebiteurServiceDep) -> None:
    await service.delete_debiteur(debiteur_id)
