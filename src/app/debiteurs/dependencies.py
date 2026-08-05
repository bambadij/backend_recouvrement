from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.debiteurs.repository import DebiteurRepository
from app.debiteurs.service import DebiteurService
from app.users.dependencies import CurrentUserDep


def get_debiteur_service(
    db: Annotated[AsyncSession, Depends(get_db)], current_user: CurrentUserDep
) -> DebiteurService:
    return DebiteurService(DebiteurRepository(db), current_user)


DebiteurServiceDep = Annotated[DebiteurService, Depends(get_debiteur_service)]
