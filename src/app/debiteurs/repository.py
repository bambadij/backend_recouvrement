from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.debiteurs.models import Debiteur
from app.debiteurs.schemas import DebiteurCreate, DebiteurUpdate


class DebiteurRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: DebiteurCreate, organisation_id: int) -> Debiteur:
        debiteur = Debiteur(**data.model_dump(), organisation_id=organisation_id)
        self.db.add(debiteur)
        await self.db.commit()
        await self.db.refresh(debiteur)
        return debiteur

    async def get_by_id(self, debiteur_id: int) -> Debiteur | None:
        return await self.db.get(Debiteur, debiteur_id)

    async def get_by_email(self, email: str, organisation_id: int) -> Debiteur | None:
        result = await self.db.execute(
            select(Debiteur).where(Debiteur.email == email, Debiteur.organisation_id == organisation_id)
        )
        return result.scalar_one_or_none()

    async def get_by_telephone(self, telephone: str, organisation_id: int) -> Debiteur | None:
        result = await self.db.execute(
            select(Debiteur)
            .where(Debiteur.telephone == telephone, Debiteur.organisation_id == organisation_id)
            .limit(1)
        )
        return result.scalars().first()

    async def list(
        self, skip: int = 0, limit: int = 100, search: str | None = None, organisation_id: int | None = None
    ) -> list[Debiteur]:
        query = select(Debiteur)
        if organisation_id is not None:
            query = query.where(Debiteur.organisation_id == organisation_id)
        if search:
            like = f"%{search}%"
            query = query.where(
                (Debiteur.nom.ilike(like)) | (Debiteur.prenom.ilike(like)) | (Debiteur.entreprise.ilike(like))
            )
        query = query.order_by(Debiteur.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, debiteur: Debiteur, data: DebiteurUpdate) -> Debiteur:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(debiteur, field, value)
        await self.db.commit()
        await self.db.refresh(debiteur)
        return debiteur

    async def delete(self, debiteur: Debiteur) -> None:
        await self.db.delete(debiteur)
        await self.db.commit()

    async def count(self, organisation_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Debiteur).where(Debiteur.organisation_id == organisation_id)
        )
        return result.scalar_one()
