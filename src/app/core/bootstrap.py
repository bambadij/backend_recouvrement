from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.users.models import RoleUtilisateur
from app.users.repository import UserRepository


async def bootstrap_super_admin(db: AsyncSession) -> None:
    """Cree le SUPER_ADMIN par defaut si SUPER_ADMIN_EMAIL/SUPER_ADMIN_PASSWORD sont
    definis dans l'environnement et qu'aucun compte n'existe deja pour cet email."""
    if not settings.super_admin_email or not settings.super_admin_password:
        return

    repository = UserRepository(db)
    if await repository.get_by_email(settings.super_admin_email):
        return

    await repository.create(
        nom="Super",
        prenom="Admin",
        email=settings.super_admin_email,
        hashed_password=hash_password(settings.super_admin_password),
        role=RoleUtilisateur.SUPER_ADMIN,
        organisation_id=None,
    )
