# La classe definit une methode « list », qui masque le type builtin du meme
# nom pour tout ce qui la suit dans le corps de la classe. Sans cet import,
# « -> list[tuple] » leve TypeError a l'import du module — meme piege que dans
# le depot des debiteurs.
from __future__ import annotations

from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.models import Client
from app.creanciers.models import Creancier
from app.dossiers.models import Dossier
from app.creanciers.schemas import CreancierCreate, CreancierUpdate


class CreancierRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour la vue plateforme."""
        return Creancier.organisation_id == organisation_id if organisation_id is not None else true()

    async def create(self, data: CreancierCreate, organisation_id: int) -> Creancier:
        creancier = Creancier(**data.model_dump(), organisation_id=organisation_id)
        self.db.add(creancier)
        await self.db.commit()
        await self.db.refresh(creancier)
        return creancier

    async def get_by_id(self, creancier_id: int) -> Creancier | None:
        return await self.db.get(Creancier, creancier_id)

    async def get_by_nom(self, nom: str, organisation_id: int) -> Creancier | None:
        result = await self.db.execute(
            select(Creancier).where(Creancier.nom == nom, Creancier.organisation_id == organisation_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self, skip: int = 0, limit: int = 100, search: str | None = None, organisation_id: int | None = None
    ) -> list[Creancier]:
        query = select(Creancier).where(self._portee(organisation_id))
        if search:
            query = query.where(Creancier.nom.ilike(f"%{search}%"))
        query = query.order_by(Creancier.nom).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, creancier: Creancier, data: CreancierUpdate) -> Creancier:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(creancier, field, value)
        await self.db.commit()
        await self.db.refresh(creancier)
        return creancier

    async def delete(self, creancier: Creancier) -> None:
        await self.db.delete(creancier)
        await self.db.commit()

    async def compter_dossiers(self, creancier_id: int) -> int:
        from app.dossiers.models import Dossier

        result = await self.db.execute(
            select(func.count()).select_from(Dossier).where(Dossier.creancier_id == creancier_id)
        )
        return int(result.scalar_one())

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Creancier).where(self._portee(organisation_id))
        )
        return int(result.scalar_one())

    async def repertoire(
        self, organisation_id: int | None, search: str | None = None
    ) -> list[tuple[str, int, str, str | None, str | None, str | None, int]]:
        """Tous ceux a qui de l'argent est du, quelle que soit la table qui les porte.

        Deux origines, reunies a la LECTURE seulement.

        Une entite propre existe dans « creanciers » : un assureur confie un
        dossier dont le creancier est l'entreprise assuree. Un client, lui, est
        son propre creancier des qu'un de ses dossiers laisse creancier_id a
        NULL — l'ecole qui recouvre ses propres impayes.

        Le stockage ne bouge pas : dupliquer l'ecole dans les deux tables
        creerait deux fiches a maintenir, et l'une deriverait au premier
        changement d'adresse. C'est l'ecran qui avait herite du stockage et
        montrait la table plutot que la realite.

        Deux requetes plutot qu'une UNION : les deux sources n'ont pas la meme
        clause de comptage, et un repertoire de tiers se compte en centaines.
        """
        entites = await self.db.execute(
            select(
                Creancier.id,
                Creancier.nom,
                Creancier.email,
                Creancier.telephone,
                Creancier.adresse,
                func.count(Dossier.id).label("nb"),
            )
            .outerjoin(Dossier, Dossier.creancier_id == Creancier.id)
            .where(self._portee(organisation_id))
            .group_by(Creancier.id)
        )

        # Un client ne figure ici que s'il est EFFECTIVEMENT creancier d'au
        # moins un dossier. Les lister tous ferait du repertoire des creanciers
        # une seconde liste de clients.
        clients = await self.db.execute(
            select(
                Client.id,
                Client.nom,
                Client.email,
                Client.telephone,
                Client.adresse,
                func.count(Dossier.id).label("nb"),
            )
            .join(Dossier, Dossier.client_id == Client.id)
            .where(
                Client.organisation_id == organisation_id if organisation_id is not None else true(),
                Dossier.creancier_id.is_(None),
            )
            .group_by(Client.id)
        )

        lignes = [("PROPRE", *ligne) for ligne in entites.all()]
        lignes += [("CLIENT", *ligne) for ligne in clients.all()]

        if search:
            motif = search.lower()
            lignes = [ligne for ligne in lignes if motif in ligne[2].lower()]
        # Tri par nom, toutes origines melangees : le repertoire se parcourt
        # alphabetiquement, pas par table d'origine.
        return sorted(lignes, key=lambda ligne: ligne[2].lower())
