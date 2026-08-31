from fastapi import APIRouter, Query, status

from app.core.security import create_access_token
from app.users.dependencies import CurrentAdminDep, CurrentUserDep, UserServiceDep
from app.users.schemas import LoginRequest, Token, UserCreate, UserRead, UserSelfUpdate, UserUpdate

auth_router = APIRouter(prefix="/auth", tags=["auth"])
router = APIRouter(prefix="/users", tags=["users"])


@auth_router.post("/login", response_model=Token)
async def login(data: LoginRequest, service: UserServiceDep) -> Token:
    user = await service.authenticate(data.email, data.password)
    return Token(access_token=create_access_token(subject=str(user.id)))


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(data: UserCreate, service: UserServiceDep, creator: CurrentAdminDep) -> UserRead:
    """Cree un utilisateur. SUPER_ADMIN : ADMIN/AGENT dans l'organisation de son choix.
    ADMIN : AGENT dans sa propre organisation uniquement."""
    user = await service.create_user(data, creator)
    return UserRead.model_validate(user)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(current_user)


@router.get("", response_model=list[UserRead])
async def list_users(
    service: UserServiceDep,
    current_admin: CurrentAdminDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[UserRead]:
    users = await service.list_users(current_admin, skip=skip, limit=limit)
    return [UserRead.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, service: UserServiceDep, current_admin: CurrentAdminDep) -> UserRead:
    user = await service.get_user_scoped(user_id, current_admin)
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(data: UserSelfUpdate, current_user: CurrentUserDep, service: UserServiceDep) -> UserRead:
    user = await service.update_me(current_user, data)
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, data: UserUpdate, service: UserServiceDep, current_admin: CurrentAdminDep
) -> UserRead:
    user = await service.update_user(user_id, data, current_admin)
    return UserRead.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, service: UserServiceDep, current_admin: CurrentAdminDep) -> None:
    await service.delete_user(user_id, current_admin)
