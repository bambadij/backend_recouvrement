from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.creances.repository import CreanceRepository
from app.creances.service import CreanceService
from app.debiteurs.dependencies import get_debiteur_service
from app.debiteurs.service import DebiteurService
from app.organisations.repository import OrganisationRepository
from app.users.dependencies import CurrentUserDep


def get_creance_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    debiteur_service: Annotated[DebiteurService, Depends(get_debiteur_service)],
    current_user: CurrentUserDep,
) -> CreanceService:
    return CreanceService(CreanceRepository(db), debiteur_service, OrganisationRepository(db), current_user)


CreanceServiceDep = Annotated[CreanceService, Depends(get_creance_service)]
