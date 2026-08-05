from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.creances.models import Creance, StatutCreance
from app.creances.schemas import CreanceCreate, CreanceUpdate


class CreanceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: CreanceCreate, organisation_id: int) -> Creance:
        creance = Creance(**data.model_dump(), montant_restant=data.montant_initial, organisation_id=organisation_id)
        self.db.add(creance)
        await self.db.commit()
        await self.db.refresh(creance)
        return creance

    async def get_by_id(self, creance_id: int) -> Creance | None:
        return await self.db.get(Creance, creance_id)

    async def count(self, organisation_id: int) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Creance).where(Creance.organisation_id == organisation_id)
        )
        return int(result.scalar_one())

    async def get_by_reference(self, reference: str, organisation_id: int) -> Creance | None:
        result = await self.db.execute(
            select(Creance).where(Creance.reference == reference, Creance.organisation_id == organisation_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        debiteur_id: int | None = None,
        statut: StatutCreance | None = None,
        organisation_id: int | None = None,
    ) -> list[Creance]:
        query = select(Creance)
        if organisation_id is not None:
            query = query.where(Creance.organisation_id == organisation_id)
        if debiteur_id is not None:
            query = query.where(Creance.debiteur_id == debiteur_id)
        if statut is not None:
            query = query.where(Creance.statut == statut)
        query = query.order_by(Creance.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, creance: Creance, data: CreanceUpdate) -> Creance:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(creance, field, value)
        await self.db.commit()
        await self.db.refresh(creance)
        return creance

    async def appliquer_paiement(self, creance: Creance, montant: Decimal) -> Creance:
        creance.montant_restant -= montant
        if creance.montant_restant <= 0:
            creance.montant_restant = Decimal("0")
            creance.statut = StatutCreance.SOLDEE
        await self.db.commit()
        await self.db.refresh(creance)
        return creance

    async def delete(self, creance: Creance) -> None:
        await self.db.delete(creance)
        await self.db.commit()

    async def count_by_statut(self, organisation_id: int) -> dict[str, int]:
        result = await self.db.execute(
            select(Creance.statut, func.count())
            .where(Creance.organisation_id == organisation_id)
            .group_by(Creance.statut)
        )
        return {statut.value: count for statut, count in result.all()}

    async def sum_montants(self, organisation_id: int) -> tuple[Decimal, Decimal]:
        result = await self.db.execute(
            select(
                func.coalesce(func.sum(Creance.montant_initial), 0),
                func.coalesce(func.sum(Creance.montant_restant), 0),
            ).where(Creance.organisation_id == organisation_id)
        )
        montant_initial, montant_restant = result.one()
        return Decimal(montant_initial), Decimal(montant_restant)
