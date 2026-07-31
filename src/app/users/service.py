from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException, UnauthorizedException
from app.core.security import hash_password, verify_password
from app.organisations.service import OrganisationService
from app.users.models import RoleUtilisateur, User
from app.users.repository import UserRepository
from app.users.schemas import UserCreate, UserSelfUpdate, UserUpdate


class UserService:
    def __init__(self, repository: UserRepository, organisation_service: OrganisationService) -> None:
        self.repository = repository
        self.organisation_service = organisation_service

    async def create_user(self, data: UserCreate, creator: User) -> User:
        if await self.repository.get_by_email(data.email):
            raise ConflictException(f"Un utilisateur avec l'email {data.email} existe deja")

        if creator.role == RoleUtilisateur.SUPER_ADMIN:
            if data.role == RoleUtilisateur.SUPER_ADMIN:
                raise BadRequestException("Impossible de creer un SUPER_ADMIN via cette route")
            if data.organisation_id is None:
                raise BadRequestException("organisation_id est requis pour creer un utilisateur")
            await self.organisation_service.get_organisation(data.organisation_id)
            role, organisation_id = data.role, data.organisation_id
        elif creator.role == RoleUtilisateur.ADMIN:
            role, organisation_id = RoleUtilisateur.AGENT, creator.organisation_id
        else:
            raise ForbiddenException("Seuls les administrateurs peuvent creer des utilisateurs")

        hashed_password = hash_password(data.password)
        return await self.repository.create(data.nom, data.prenom, data.email, hashed_password, role, organisation_id)

    async def authenticate(self, email: str, password: str) -> User:
        user = await self.repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedException("Email ou mot de passe incorrect")
        if not user.is_active:
            raise UnauthorizedException("Ce compte est desactive")
        return user

    async def get_user(self, user_id: int) -> User:
        user = await self.repository.get_by_id(user_id)
        if user is None:
            raise NotFoundException(f"Utilisateur {user_id} introuvable")
        return user

    async def get_user_scoped(self, user_id: int, current_admin: User) -> User:
        user = await self.get_user(user_id)
        if current_admin.role != RoleUtilisateur.SUPER_ADMIN and user.organisation_id != current_admin.organisation_id:
            raise NotFoundException(f"Utilisateur {user_id} introuvable")
        return user

    async def list_users(self, current_admin: User, skip: int = 0, limit: int = 100) -> list[User]:
        organisation_id = (
            None if current_admin.role == RoleUtilisateur.SUPER_ADMIN else current_admin.organisation_id
        )
        return await self.repository.list(skip=skip, limit=limit, organisation_id=organisation_id)

    async def update_user(self, user_id: int, data: UserUpdate, current_admin: User) -> User:
        user = await self.get_user_scoped(user_id, current_admin)

        if current_admin.role == RoleUtilisateur.SUPER_ADMIN:
            if data.role == RoleUtilisateur.SUPER_ADMIN:
                raise BadRequestException("Impossible de promouvoir un utilisateur en SUPER_ADMIN via cette route")
        else:
            if data.organisation_id is not None:
                raise ForbiddenException("Seul un SUPER_ADMIN peut changer l'organisation d'un utilisateur")
            if data.role is not None and data.role != RoleUtilisateur.AGENT:
                raise ForbiddenException("Un administrateur ne peut promouvoir un utilisateur qu'au rang AGENT")

        hashed_password = hash_password(data.password) if data.password else None
        return await self.repository.update(user, data, hashed_password)

    async def update_me(self, user: User, data: UserSelfUpdate) -> User:
        """Mise a jour de son propre compte : profil et mot de passe, rien d'autre."""
        hashed_password = None
        if data.nouveau_mot_de_passe:
            if not data.mot_de_passe_actuel:
                raise BadRequestException("Le mot de passe actuel est requis pour en definir un nouveau")
            if not verify_password(data.mot_de_passe_actuel, user.hashed_password):
                raise BadRequestException("Mot de passe actuel incorrect")
            hashed_password = hash_password(data.nouveau_mot_de_passe)

        return await self.repository.update_profil(user, data.nom, data.prenom, hashed_password)

    async def delete_user(self, user_id: int, current_admin: User) -> None:
        user = await self.get_user_scoped(user_id, current_admin)
        await self.repository.delete(user)
