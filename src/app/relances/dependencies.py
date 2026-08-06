from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.debiteurs.dependencies import get_debiteur_service
from app.debiteurs.service import DebiteurService
from app.dossiers.dependencies import get_dossier_service
from app.dossiers.service import DossierService
from app.relances.repository import RelanceRepository
from app.relances.service import RelanceService
from app.users.dependencies import CurrentUserDep


def get_relance_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    dossier_service: Annotated[DossierService, Depends(get_dossier_service)],
    debiteur_service: Annotated[DebiteurService, Depends(get_debiteur_service)],
    current_user: CurrentUserDep,
) -> RelanceService:
    return RelanceService(RelanceRepository(db), dossier_service, debiteur_service, current_user)


RelanceServiceDep = Annotated[RelanceService, Depends(get_relance_service)]
