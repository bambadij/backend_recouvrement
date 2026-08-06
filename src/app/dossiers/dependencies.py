from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.dependencies import get_client_service
from app.clients.service import ClientService
from app.core.database import get_db
from app.creanciers.dependencies import get_creancier_service
from app.creanciers.service import CreancierService
from app.dossiers.repository import DossierRepository
from app.dossiers.service import DossierService
from app.users.dependencies import CurrentUserDep


def get_dossier_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    client_service: Annotated[ClientService, Depends(get_client_service)],
    creancier_service: Annotated[CreancierService, Depends(get_creancier_service)],
    current_user: CurrentUserDep,
) -> DossierService:
    return DossierService(DossierRepository(db), client_service, creancier_service, current_user)


DossierServiceDep = Annotated[DossierService, Depends(get_dossier_service)]
