from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.creances.dependencies import get_creance_service
from app.creances.service import CreanceService
from app.paiements.repository import PaiementRepository
from app.paiements.service import PaiementService
from app.users.dependencies import CurrentUserDep


def get_paiement_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    creance_service: Annotated[CreanceService, Depends(get_creance_service)],
    current_user: CurrentUserDep,
) -> PaiementService:
    return PaiementService(PaiementRepository(db), creance_service, current_user)


PaiementServiceDep = Annotated[PaiementService, Depends(get_paiement_service)]
