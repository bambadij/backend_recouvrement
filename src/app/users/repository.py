from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import RoleUtilisateur, User
from app.users.schemas import UserUpdate


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

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
            query = query.where(User.organisation_id == organisation_id)
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

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.commit()

    async def count(self, organisation_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(User.organisation_id == organisation_id)
        )
        return result.scalar_one()
