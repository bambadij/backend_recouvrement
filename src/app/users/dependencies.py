from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.ia.journal import Appelant, appelant
from app.organisations.dependencies import get_organisation_service
from app.organisations.service import OrganisationService
from app.users.models import RoleUtilisateur, User
from app.users.repository import UserRepository
from app.users.service import UserService

bearer_scheme = HTTPBearer()


def get_user_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    organisation_service: Annotated[OrganisationService, Depends(get_organisation_service)],
) -> UserService:
    return UserService(UserRepository(db), organisation_service)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    service: UserServiceDep,
) -> User:
    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise UnauthorizedException("Token invalide ou expire")
    utilisateur = await service.get_user(int(payload["sub"]))

    # Qui appelle, pour le journal de consommation des modeles. Pose ici parce
    # que c'est le seul point par ou passe toute requete authentifiee : les six
    # fonctions qui appellent un modele ont des signatures differentes et n'ont
    # pour la plupart aucune raison de connaitre l'utilisateur. Leur imposer un
    # argument de comptabilite melangerait la mesure au metier.
    appelant.set(
        Appelant(
            organisation_id=utilisateur.organisation_id,
            agent_nom=f"{utilisateur.prenom} {utilisateur.nom}".strip() or None,
        )
    )
    return utilisateur


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def get_current_admin(current_user: CurrentUserDep) -> User:
    """ADMIN (de son organisation) ou SUPER_ADMIN (transverse)."""
    if current_user.role not in (RoleUtilisateur.ADMIN, RoleUtilisateur.SUPER_ADMIN):
        raise ForbiddenException("Reserve aux administrateurs")
    return current_user


CurrentAdminDep = Annotated[User, Depends(get_current_admin)]


async def get_current_super_admin(current_user: CurrentUserDep) -> User:
    if current_user.role != RoleUtilisateur.SUPER_ADMIN:
        raise ForbiddenException("Reserve au super-administrateur")
    return current_user


CurrentSuperAdminDep = Annotated[User, Depends(get_current_super_admin)]
