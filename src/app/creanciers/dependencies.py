from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.creanciers.repository import CreancierRepository
from app.creanciers.service import CreancierService
from app.users.dependencies import CurrentUserDep


def get_creancier_service(
    db: Annotated[AsyncSession, Depends(get_db)], current_user: CurrentUserDep
) -> CreancierService:
    return CreancierService(CreancierRepository(db), current_user)


CreancierServiceDep = Annotated[CreancierService, Depends(get_creancier_service)]
