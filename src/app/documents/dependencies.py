from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.creances.dependencies import get_creance_service
from app.creances.service import CreanceService
from app.documents.repository import DocumentRepository
from app.documents.service import DocumentService
from app.dossiers.dependencies import get_dossier_service
from app.dossiers.service import DossierService
from app.paiements.repository import PaiementRepository
from app.users.dependencies import CurrentUserDep


def get_document_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    dossier_service: Annotated[DossierService, Depends(get_dossier_service)],
    creance_service: Annotated[CreanceService, Depends(get_creance_service)],
    current_user: CurrentUserDep,
) -> DocumentService:
    return DocumentService(
        DocumentRepository(db), dossier_service, creance_service, PaiementRepository(db), current_user
    )


DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]
