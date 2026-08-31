from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.creances.repository import CreanceRepository
from app.dossiers.dependencies import get_dossier_service
from app.dossiers.service import DossierService
from app.ia.promesses import ExtractionPromessesIA, get_extraction_promesses_ia
from app.paiements.repository import PaiementRepository
from app.promesses.repository import PromesseRepository
from app.promesses.service import PromesseService
from app.relances.repository import RelanceRepository
from app.users.dependencies import CurrentUserDep


def get_promesse_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    dossier_service: Annotated[DossierService, Depends(get_dossier_service)],
    extraction: Annotated[ExtractionPromessesIA, Depends(get_extraction_promesses_ia)],
    current_user: CurrentUserDep,
) -> PromesseService:
    return PromesseService(
        PromesseRepository(db),
        PaiementRepository(db),
        RelanceRepository(db),
        CreanceRepository(db),
        dossier_service,
        extraction,
        current_user,
    )


PromesseServiceDep = Annotated[PromesseService, Depends(get_promesse_service)]
