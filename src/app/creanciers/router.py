from fastapi import APIRouter, Query, status

from app.creanciers.dependencies import CreancierServiceDep
from app.creanciers.schemas import (
    CreancierCreate,
    CreancierRead,
    CreancierRepertoire,
    CreancierUpdate,
)
from app.users.dependencies import CurrentAdminDep

router = APIRouter(prefix="/creanciers", tags=["creanciers"])


# Referentiel : creation et suppression reservees a l'ADMIN.
@router.post("", response_model=CreancierRead, status_code=status.HTTP_201_CREATED)
async def create_creancier(
    data: CreancierCreate, service: CreancierServiceDep, _: CurrentAdminDep
) -> CreancierRead:
    creancier = await service.create_creancier(data)
    return CreancierRead.model_validate(creancier)


@router.get("", response_model=list[CreancierRead])
async def list_creanciers(
    service: CreancierServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: str | None = None,
) -> list[CreancierRead]:
    creanciers = await service.list_creanciers(skip=skip, limit=limit, search=search)
    return [CreancierRead.model_validate(c) for c in creanciers]


# Declare avant « /{creancier_id} » : sinon « repertoire » serait pris pour un
# identifiant et la route repondrait 422.
@router.get("/repertoire", response_model=list[CreancierRepertoire])
async def repertoire_creanciers(
    service: CreancierServiceDep,
    search: str | None = None,
) -> list[CreancierRepertoire]:
    """Tous ceux a qui de l'argent est du, quelle que soit la table qui les porte.

    La liste « creanciers » ne montrait que la table du meme nom. Une ecole qui
    recouvre ses propres impayes est pourtant creanciere de ses dossiers, sans
    y figurer : le dossier laisse creancier_id a NULL plutot que de dupliquer
    l'entite. L'ecran avait herite du stockage et montrait la table au lieu de
    la realite.

    Distinct de GET /creanciers, qui ne rend que les entites propres — les
    seules qu'on puisse choisir comme creancier d'un dossier.
    """
    return await service.repertoire(search=search)


@router.get("/{creancier_id}", response_model=CreancierRead)
async def get_creancier(creancier_id: int, service: CreancierServiceDep) -> CreancierRead:
    creancier = await service.get_creancier(creancier_id)
    return CreancierRead.model_validate(creancier)


@router.patch("/{creancier_id}", response_model=CreancierRead)
async def update_creancier(
    creancier_id: int, data: CreancierUpdate, service: CreancierServiceDep
) -> CreancierRead:
    creancier = await service.update_creancier(creancier_id, data)
    return CreancierRead.model_validate(creancier)


@router.delete("/{creancier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creancier(creancier_id: int, service: CreancierServiceDep, _: CurrentAdminDep) -> None:
    await service.delete_creancier(creancier_id)
