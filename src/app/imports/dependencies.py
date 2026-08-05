from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.creances.dependencies import get_creance_service
from app.creances.service import CreanceService
from app.debiteurs.repository import DebiteurRepository
from app.imports.service import ImportService
from app.users.dependencies import CurrentUserDep


def get_import_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    creance_service: Annotated[CreanceService, Depends(get_creance_service)],
    current_user: CurrentUserDep,
) -> ImportService:
    return ImportService(DebiteurRepository(db), creance_service, current_user)


ImportServiceDep = Annotated[ImportService, Depends(get_import_service)]
