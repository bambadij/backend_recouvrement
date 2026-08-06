# Annotations differees : la methode `list` de ce repository masque le type
# `list` dans le corps de la classe.
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.creances.models import Creance, StatutCreance
from app.relances.models import Relance, StatutRelance
from app.relances.schemas import RelanceCreate, RelanceUpdate


class RelanceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour une vue plateforme.

        organisation_id None signifie « toutes les organisations » : le SUPER_ADMIN
        consulte alors le parc entier. Renvoyer true() plutot que d'omettre la clause
        garde la forme des requetes identique dans les deux cas.
        """
        return Relance.organisation_id == organisation_id if organisation_id is not None else true()


    async def create(
        self, data: RelanceCreate, organisation_id: int | None, cree_par_nom: str | None = None
    ) -> Relance:
        relance = Relance(
            **data.model_dump(), organisation_id=organisation_id, cree_par_nom=cree_par_nom
        )
        self.db.add(relance)
        await self.db.commit()
        await self.db.refresh(relance)
        return relance

    async def get_by_id(self, relance_id: int) -> Relance | None:
        return await self.db.get(Relance, relance_id)

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        dossier_id: int | None = None,
        debiteur_id: int | None = None,
        organisation_id: int | None = None,
        statut: StatutRelance | None = None,
        avec_resultat: bool | None = None,
    ) -> list[Relance]:
        query = select(Relance)
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
        if dossier_id is not None:
            query = query.where(Relance.dossier_id == dossier_id)
        if debiteur_id is not None:
            query = query.where(Relance.debiteur_id == debiteur_id)
        if statut is not None:
            query = query.where(Relance.statut == statut)
        if avec_resultat is not None:
            # Un resultat renseigne = un engagement obtenu du debiteur, a recontroler.
            # La chaine vide compte comme absent : sinon un champ efface passerait pour
            # une promesse.
            renseigne = Relance.resultat.isnot(None) & (Relance.resultat != "")
            query = query.where(renseigne if avec_resultat else ~renseigne)
        query = query.order_by(Relance.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, relance: Relance, data: RelanceUpdate) -> Relance:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(relance, field, value)
        await self.db.commit()
        await self.db.refresh(relance)
        return relance

    async def delete(self, relance: Relance) -> None:
        await self.db.delete(relance)
        await self.db.commit()

    async def activite_par_agent(self, organisation_id: int | None) -> dict[str, tuple[int, int]]:
        """Par agent : relances emises et relances ayant obtenu un retour.

        Le retour (champ resultat renseigne) est le seul signal d'aboutissement
        disponible sur une relance : il distingue l'agent qui obtient une reponse
        de celui qui envoie dans le vide.
        """
        renseigne = Relance.resultat.isnot(None) & (Relance.resultat != "")
        result = await self.db.execute(
            select(Relance.cree_par_nom, func.count(), func.count().filter(renseigne))
            .where(self._portee(organisation_id), Relance.cree_par_nom.isnot(None))
            .group_by(Relance.cree_par_nom)
        )
        return {row[0]: (row[1], row[2]) for row in result.all()}

    async def creances_sans_relance_depuis(
        self, organisation_id: int | None, jours: int
    ) -> list[tuple[int, str, Decimal, int, bool]]:
        """Creances actives laissees sans relance depuis plus de `jours`.

        Renvoie (id, reference, montant, jours, jamais_relancee).

        Une creance est consideree relancee des qu'une relance a vise SON debiteur
        dans SON dossier, meme si elle portait sur une autre de ses factures : un
        seul courrier couvre tous les impayes de ce debiteur dans ce dossier.

        Les deux cas ne se mesurent pas sur la meme horloge, et les confondre
        ferait afficher un nombre invente :
        - deja relance -> jours ecoules depuis la derniere relance ;
        - jamais relance -> jours de RETARD depuis l'echeance. C'est le signal
          operationnel : un dossier echu depuis 40 jours que personne n'a
          jamais contacte est anormal, quelle que soit sa date d'entree en base.
        """
        aujourdhui = date.today()
        derniere = (
            select(
                Relance.dossier_id,
                Relance.debiteur_id,
                func.max(Relance.date_relance).label("derniere"),
            )
            .group_by(Relance.dossier_id, Relance.debiteur_id)
            .subquery()
        )
        result = await self.db.execute(
            select(
                Creance.id,
                Creance.reference,
                Creance.montant_restant,
                Creance.date_echeance,
                derniere.c.derniere,
            )
            .outerjoin(
                derniere,
                (derniere.c.dossier_id == Creance.dossier_id)
                & (derniere.c.debiteur_id == Creance.debiteur_id),
            )
            .where(
                Creance.organisation_id == organisation_id
                if organisation_id is not None
                else true(),
                Creance.statut.in_((StatutCreance.EN_COURS, StatutCreance.EN_RETARD)),
                Creance.montant_restant > 0,
            )
        )
        lignes: list[tuple[int, str, Decimal, int, bool]] = []
        for cid, ref, montant, echeance, derniere_date in result.all():
            jamais = derniere_date is None
            ecart = (aujourdhui - (derniere_date or echeance)).days
            if ecart > jours:
                lignes.append((cid, ref, Decimal(montant), ecart, jamais))
        return lignes

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Relance).where(self._portee(organisation_id))
        )
        return result.scalar_one()
