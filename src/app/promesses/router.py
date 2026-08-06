from fastapi import APIRouter, Query, status

from app.promesses.dependencies import PromesseServiceDep
from app.promesses.models import StatutPromesse
from app.promesses.schemas import (
    ControlePromessesResult,
    ExtractionPromessesResult,
    PromesseCreate,
    PromesseRead,
    PromesseUpdate,
)

router = APIRouter(prefix="/promesses", tags=["promesses"])


@router.post("", response_model=PromesseRead, status_code=status.HTTP_201_CREATED)
async def create_promesse(data: PromesseCreate, service: PromesseServiceDep) -> PromesseRead:
    promesse = await service.create_promesse(data)
    return PromesseRead.model_validate(promesse)


@router.get("", response_model=list[PromesseRead])
async def list_promesses(
    service: PromesseServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    dossier_id: int | None = None,
    statut: StatutPromesse | None = None,
) -> list[PromesseRead]:
    promesses = await service.list_promesses(skip=skip, limit=limit, dossier_id=dossier_id, statut=statut)
    return [PromesseRead.model_validate(p) for p in promesses]


@router.post("/controle", response_model=ControlePromessesResult)
async def controler_promesses(service: PromesseServiceDep) -> ControlePromessesResult:
    """Confronte les promesses echues aux encaissements et met a jour leur statut.

    Sans appel de modele : c'est un rapprochement comptable.
    """
    return await service.controler_echues()


@router.post("/extraction", response_model=ExtractionPromessesResult)
async def extraire_promesses(
    service: PromesseServiceDep,
    limite: int = Query(200, ge=1, le=500),
) -> ExtractionPromessesResult:
    """Relit les comptes rendus de relance et en tire les engagements datables.

    Les promesses creees ici portent source=INFEREE : ce sont des lectures
    automatiques de texte libre, pas des faits rapportes par un agent.
    """
    return await service.extraire_depuis_relances(limite=limite)


@router.get("/{promesse_id}", response_model=PromesseRead)
async def get_promesse(promesse_id: int, service: PromesseServiceDep) -> PromesseRead:
    promesse = await service.get_promesse(promesse_id)
    return PromesseRead.model_validate(promesse)


@router.patch("/{promesse_id}", response_model=PromesseRead)
async def update_promesse(
    promesse_id: int, data: PromesseUpdate, service: PromesseServiceDep
) -> PromesseRead:
    promesse = await service.update_promesse(promesse_id, data)
    return PromesseRead.model_validate(promesse)


@router.delete("/{promesse_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promesse(promesse_id: int, service: PromesseServiceDep) -> None:
    await service.delete_promesse(promesse_id)
