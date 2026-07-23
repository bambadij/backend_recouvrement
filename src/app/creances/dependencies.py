from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.dependencies import get_client_service
from app.clients.service import ClientService
from app.core.database import get_db
from app.creances.repository import CreanceRepository
from app.creances.service import CreanceService
from app.users.dependencies import CurrentUserDep


def get_creance_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    client_service: Annotated[ClientService, Depends(get_client_service)],
    current_user: CurrentUserDep,
) -> CreanceService:
    return CreanceService(CreanceRepository(db), client_service, current_user)


CreanceServiceDep = Annotated[CreanceService, Depends(get_creance_service)]
