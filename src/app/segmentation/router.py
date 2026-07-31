from fastapi import APIRouter, Query

from app.segmentation.dependencies import SegmentationServiceDep
from app.segmentation.schemas import (
    DossierSegmente,
    SegmentationRequest,
    SegmentationRunResult,
)

router = APIRouter(prefix="/segmentation", tags=["segmentation"])


@router.post("/run", response_model=SegmentationRunResult)
async def lancer_segmentation(
    data: SegmentationRequest, service: SegmentationServiceDep
) -> SegmentationRunResult:
    """Classe les dossiers actifs et enregistre le resultat.

    Passe couteuse (un appel de modele par lot de 25) : a declencher a la demande
    ou sur planification, pas a chaque affichage de liste.
    """
    return await service.lancer(data)


@router.get("/file", response_model=list[DossierSegmente])
async def file_de_travail(
    service: SegmentationServiceDep,
    limit: int = Query(200, ge=1, le=500),
) -> list[DossierSegmente]:
    """La file de travail : dossiers classes, ordonnes par priorite de traitement.

    Lecture pure — aucun appel de modele, le classement vient de la base.
    """
    return await service.file_de_travail(limit=limit)
