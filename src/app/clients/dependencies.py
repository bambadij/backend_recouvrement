from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.repository import ClientRepository
from app.clients.service import ClientService
from app.core.database import get_db
from app.users.dependencies import CurrentUserDep


def get_client_service(db: Annotated[AsyncSession, Depends(get_db)], current_user: CurrentUserDep) -> ClientService:
    return ClientService(ClientRepository(db), current_user)


ClientServiceDep = Annotated[ClientService, Depends(get_client_service)]
