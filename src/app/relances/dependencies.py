from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.creances.dependencies import get_creance_service
from app.creances.service import CreanceService
from app.relances.repository import RelanceRepository
from app.relances.service import RelanceService
from app.users.dependencies import CurrentUserDep


def get_relance_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    creance_service: Annotated[CreanceService, Depends(get_creance_service)],
    current_user: CurrentUserDep,
) -> RelanceService:
    return RelanceService(RelanceRepository(db), creance_service, current_user)


RelanceServiceDep = Annotated[RelanceService, Depends(get_relance_service)]
