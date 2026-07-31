# Les annotations sont differees : la methode `list` de ce repository masque le
# type `list` dans le corps de la classe, ce qui casserait `-> list[Promesse]`.
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.promesses.models import Promesse, SourcePromesse, StatutPromesse
from app.relances.models import Relance
from app.promesses.schemas import PromesseCreate, PromesseUpdate


class PromesseRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour une vue plateforme."""
        return Promesse.organisation_id == organisation_id if organisation_id is not None else true()

    async def create(
        self,
        data: PromesseCreate,
        organisation_id: int,
        source: SourcePromesse = SourcePromesse.SAISIE,
    ) -> Promesse:
        promesse = Promesse(**data.model_dump(), organisation_id=organisation_id, source=source)
        self.db.add(promesse)
        await self.db.commit()
        await self.db.refresh(promesse)
        return promesse

    async def create_many(self, promesses: list[Promesse]) -> list[Promesse]:
        """Insertion groupee : l'inference produit N promesses en une passe."""
        self.db.add_all(promesses)
        await self.db.commit()
        for promesse in promesses:
            await self.db.refresh(promesse)
        return promesses

    async def get_by_id(self, promesse_id: int) -> Promesse | None:
        return await self.db.get(Promesse, promesse_id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        creance_id: int | None = None,
        organisation_id: int | None = None,
        statut: StatutPromesse | None = None,
    ) -> list[Promesse]:
        query = select(Promesse)
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
        if creance_id is not None:
            query = query.where(Promesse.creance_id == creance_id)
        if statut is not None:
            query = query.where(Promesse.statut == statut)
        query = query.order_by(Promesse.date_echeance_promesse.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_relance_ids_deja_traites(self, organisation_id: int | None) -> set[int]:
        """Relances ayant deja produit une promesse.

        Sert a rendre l'inference idempotente : rejouer l'extraction ne doit pas
        dupliquer les engagements deja extraits.
        """
        query = select(Promesse.relance_id).where(Promesse.relance_id.isnot(None))
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
        result = await self.db.execute(query)
        return {row for row in result.scalars().all() if row is not None}

    async def list_a_controler(self, organisation_id: int | None, jusqu_au: date) -> list[Promesse]:
        """Promesses encore ATTENDUE dont la date d'echeance est passee."""
        query = select(Promesse).where(
            self._portee(organisation_id),
            Promesse.statut == StatutPromesse.ATTENDUE,
            Promesse.date_echeance_promesse <= jusqu_au,
        )
        result = await self.db.execute(query.order_by(Promesse.date_echeance_promesse))
        return list(result.scalars().all())

    async def update(self, promesse: Promesse, data: PromesseUpdate) -> Promesse:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(promesse, field, value)
        await self.db.commit()
        await self.db.refresh(promesse)
        return promesse

    async def delete(self, promesse: Promesse) -> None:
        await self.db.delete(promesse)
        await self.db.commit()

    async def statistiques(self, organisation_id: int | None) -> tuple[dict[str, int], Decimal]:
        """Compte des promesses par statut, et montant encore engagé (ATTENDUE).

        Le montant attendu ne retient que les engagements non encore échus ou non
        encore contrôlés : c'est ce qui alimente la prévision d'encaissement.
        """
        result = await self.db.execute(
            select(Promesse.statut, func.count(), func.coalesce(func.sum(Promesse.montant_promis), 0))
            .where(self._portee(organisation_id))
            .group_by(Promesse.statut)
        )
        par_statut: dict[str, int] = {}
        montant_attendu = Decimal(0)
        for statut, nombre, montant in result.all():
            par_statut[statut.value] = nombre
            if statut == StatutPromesse.ATTENDUE:
                montant_attendu = Decimal(montant)
        return par_statut, montant_attendu

    async def engagements_par_mois(self, organisation_id: int | None) -> dict[str, Decimal]:
        """Montants promis encore attendus, groupés par mois d'échéance promise."""
        mois = func.to_char(Promesse.date_echeance_promesse, "YYYY-MM")
        result = await self.db.execute(
            select(mois.label("mois"), func.coalesce(func.sum(Promesse.montant_promis), 0))
            .where(self._portee(organisation_id), Promesse.statut == StatutPromesse.ATTENDUE)
            .group_by(mois)
            .order_by(mois)
        )
        return {row[0]: Decimal(row[1]) for row in result.all()}

    async def obtenues_par_agent(self, organisation_id: int | None) -> dict[str, tuple[int, int]]:
        """Par agent : promesses obtenues et promesses tenues.

        L'agent est celui qui a émis la relance d'où sort l'engagement ; les
        promesses sans relance rattachée sont ignorées, faute d'auteur.
        """
        result = await self.db.execute(
            select(
                Relance.cree_par_nom,
                func.count(),
                func.count().filter(Promesse.statut == StatutPromesse.TENUE),
            )
            .join(Relance, Promesse.relance_id == Relance.id)
            .where(self._portee(organisation_id), Relance.cree_par_nom.isnot(None))
            .group_by(Relance.cree_par_nom)
        )
        return {row[0]: (row[1], row[2]) for row in result.all()}

    async def commit(self) -> None:
        """Valide des modifications faites directement sur les entites chargees."""
        await self.db.commit()

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Promesse).where(self._portee(organisation_id))
        )
        return result.scalar_one()
