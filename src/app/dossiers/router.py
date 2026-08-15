from fastapi import APIRouter, Query, status

from app.dossiers.dependencies import DossierServiceDep
from app.dossiers.models import StatutDossier
from app.dossiers.schemas import (
    AnalyseDossier,
    DossierCreate,
    DossierListItem,
    DossierRead,
    DossierUpdate,
    FaitsDossier,
)
from app.ia.dependencies import AnalyseDossierIADep
from app.users.dependencies import CurrentAdminDep

router = APIRouter(prefix="/dossiers", tags=["dossiers"])


# Referentiel : ouvrir un dossier engage l'organisation vis-a-vis du client, et
# le supprimer efface une demande recue. Reserve a l'ADMIN.
@router.post("", response_model=DossierRead, status_code=status.HTTP_201_CREATED)
async def create_dossier(data: DossierCreate, service: DossierServiceDep) -> DossierRead:
    dossier = await service.create_dossier(data)
    return DossierRead.model_validate(dossier)


@router.get("", response_model=list[DossierListItem])
async def list_dossiers(
    service: DossierServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    client_id: int | None = None,
    creancier_id: int | None = None,
    statut: StatutDossier | None = None,
) -> list[DossierListItem]:
    return await service.list_dossiers(
        skip=skip, limit=limit, client_id=client_id, creancier_id=creancier_id, statut=statut
    )


@router.get("/{dossier_id}", response_model=DossierRead)
async def get_dossier(dossier_id: int, service: DossierServiceDep) -> DossierRead:
    dossier = await service.get_dossier(dossier_id)
    return DossierRead.model_validate(dossier)


@router.patch("/{dossier_id}", response_model=DossierRead)
async def update_dossier(dossier_id: int, data: DossierUpdate, service: DossierServiceDep) -> DossierRead:
    dossier = await service.update_dossier(dossier_id, data)
    return DossierRead.model_validate(dossier)


@router.delete("/{dossier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dossier(dossier_id: int, service: DossierServiceDep, _: CurrentAdminDep) -> None:
    await service.delete_dossier(dossier_id)


@router.get("/{dossier_id}/faits", response_model=FaitsDossier)
async def faits_dossier(dossier_id: int, service: DossierServiceDep) -> FaitsDossier:
    """L'etat chiffre du dossier. Lecture pure, aucun appel de modele."""
    return await service.faits_dossier(dossier_id)


@router.post("/{dossier_id}/analyse", response_model=AnalyseDossier)
async def analyser_dossier(
    dossier_id: int, service: DossierServiceDep, analyse_ia: AnalyseDossierIADep
) -> AnalyseDossier:
    """Analyse le dossier : synthese et actions priorisees.

    POST et non GET : la passe appelle un modele et se paie. Comme les
    recommandations du tableau de bord, elle se declenche a la demande et jamais
    a l'affichage d'une liste.

    Les faits sont renvoyes avec l'analyse : chaque action cite un chiffre, et
    l'agent doit pouvoir le confronter.
    """
    return await service.analyser_dossier(dossier_id, analyse_ia)
