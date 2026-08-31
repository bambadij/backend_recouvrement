from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import RoleUtilisateur, User
from app.users.schemas import UserUpdate


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour une vue plateforme.

        organisation_id None signifie « toutes les organisations » : le SUPER_ADMIN
        consulte alors le parc entier. Renvoyer true() plutot que d'omettre la clause
        garde la forme des requetes identique dans les deux cas.
        """
        return User.organisation_id == organisation_id if organisation_id is not None else true()


    async def create(
        self,
        nom: str,
        prenom: str,
        email: str,
        hashed_password: str,
        role: RoleUtilisateur,
        organisation_id: int | None,
    ) -> User:
        user = User(
            nom=nom,
            prenom=prenom,
            email=email,
            hashed_password=hashed_password,
            role=role,
            organisation_id=organisation_id,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list(
        self, skip: int = 0, limit: int = 100, organisation_id: int | None = None
    ) -> list[User]:
        query = select(User)
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
        query = query.order_by(User.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, user: User, data: UserUpdate, hashed_password: str | None) -> User:
        updates = data.model_dump(exclude_unset=True, exclude={"password"})
        for field, value in updates.items():
            setattr(user, field, value)
        if hashed_password is not None:
            user.hashed_password = hashed_password
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update_profil(
        self, user: User, nom: str | None, prenom: str | None, hashed_password: str | None
    ) -> User:
        """Ecrit uniquement les champs de profil, nommes un par un.

        Pas de model_dump() ici, contrairement a update() : passer un dict au
        setattr ouvrirait la porte a l'ecriture de tout champ present dans le
        payload, role compris.
        """
        if nom is not None:
            user.nom = nom
        if prenom is not None:
            user.prenom = prenom
        if hashed_password is not None:
            user.hashed_password = hashed_password
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.commit()

    async def count_par_organisation(self) -> dict[int, int]:
        """Nombre d'utilisateurs par organisation, en une requete pour toutes."""
        result = await self.db.execute(
            select(User.organisation_id, func.count())
            .where(User.organisation_id.isnot(None))
            .group_by(User.organisation_id)
        )
        return {org: nb for org, nb in result.all()}

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(self._portee(organisation_id))
        )
        return result.scalar_one()
