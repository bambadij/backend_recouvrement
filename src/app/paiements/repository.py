from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.paiements.models import Paiement
from app.paiements.schemas import PaiementCreate


class PaiementRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self, data: PaiementCreate, organisation_id: int, saisi_par_nom: str | None = None
    ) -> Paiement:
        paiement = Paiement(**data.model_dump(), organisation_id=organisation_id, saisi_par_nom=saisi_par_nom)
        self.db.add(paiement)
        await self.db.commit()
        await self.db.refresh(paiement)
        return paiement

    async def get_by_id(self, paiement_id: int) -> Paiement | None:
        return await self.db.get(Paiement, paiement_id)

    async def list(
        self, skip: int = 0, limit: int = 100, creance_id: int | None = None, organisation_id: int | None = None
    ) -> list[Paiement]:
        query = select(Paiement)
        if organisation_id is not None:
            query = query.where(Paiement.organisation_id == organisation_id)
        if creance_id is not None:
            query = query.where(Paiement.creance_id == creance_id)
        query = query.order_by(Paiement.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def stats(self, organisation_id: int) -> tuple[int, Decimal]:
        result = await self.db.execute(
            select(func.count(), func.coalesce(func.sum(Paiement.montant), 0)).where(
                Paiement.organisation_id == organisation_id
            )
        )
        count, total = result.one()
        return count, Decimal(total)
