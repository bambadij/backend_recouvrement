# Les annotations sont evaluees paresseusement : la classe definit une methode
# « list », qui masque le type builtin du meme nom pour tout ce qui la suit dans
# le corps de la classe. Sans cet import, « -> list[tuple] » leve TypeError a
# l'import du module.
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.creances.models import Creance
from app.debiteurs.models import Debiteur
from app.debiteurs.schemas import DebiteurCreate, DebiteurUpdate
from app.debiteurs.telephone import normaliser
from app.paiements.models import Paiement
from app.promesses.models import Promesse
from app.relances.models import Relance


class DebiteurRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _portee(organisation_id: int | None):
        """Filtre d'organisation, ou predicat neutre pour une vue plateforme.

        organisation_id None signifie « toutes les organisations » : le SUPER_ADMIN
        consulte alors le parc entier. Renvoyer true() plutot que d'omettre la clause
        garde la forme des requetes identique dans les deux cas.
        """
        return Debiteur.organisation_id == organisation_id if organisation_id is not None else true()

    async def create(self, data: DebiteurCreate, organisation_id: int | None) -> Debiteur:
        champs = data.model_dump()
        # La forme canonique est derivee ici, jamais fournie par l'appelant : elle
        # doit rester en phase avec « telephone » quel que soit le chemin d'entree.
        champs["telephone_normalise"] = normaliser(champs.get("telephone"))
        debiteur = Debiteur(**champs, organisation_id=organisation_id)
        self.db.add(debiteur)
        await self.db.commit()
        await self.db.refresh(debiteur)
        return debiteur

    async def get_by_id(self, debiteur_id: int) -> Debiteur | None:
        return await self.db.get(Debiteur, debiteur_id)

    async def get_by_email(self, email: str, organisation_id: int | None) -> Debiteur | None:
        result = await self.db.execute(
            select(Debiteur).where(Debiteur.email == email, self._portee(organisation_id))
        )
        return result.scalar_one_or_none()

    async def get_by_telephone(self, telephone: str, organisation_id: int | None) -> Debiteur | None:
        """Recherche sur la forme canonique : « +221 77 000 11 11 » retrouve « 770001111 »."""
        canonique = normaliser(telephone)
        if canonique is None:
            return None
        result = await self.db.execute(
            select(Debiteur)
            .where(Debiteur.telephone_normalise == canonique, self._portee(organisation_id))
            .limit(1)
        )
        return result.scalars().first()

    async def list(
        self, skip: int = 0, limit: int = 100, search: str | None = None, organisation_id: int | None = None
    ) -> list[Debiteur]:
        query = select(Debiteur)
        if organisation_id is not None:
            query = query.where(self._portee(organisation_id))
        if search:
            like = f"%{search}%"
            query = query.where(
                (Debiteur.nom.ilike(like)) | (Debiteur.prenom.ilike(like)) | (Debiteur.entreprise.ilike(like))
            )
        query = query.order_by(Debiteur.id).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, debiteur: Debiteur, data: DebiteurUpdate) -> Debiteur:
        modifies = data.model_dump(exclude_unset=True)
        for field, value in modifies.items():
            setattr(debiteur, field, value)
        if "telephone" in modifies:
            debiteur.telephone_normalise = normaliser(modifies["telephone"])
        await self.db.commit()
        await self.db.refresh(debiteur)
        return debiteur

    async def rollback(self) -> None:
        """Annule la transaction en cours.

        Indispensable apres une violation de contrainte pendant un import : sans
        cela la session reste en echec et TOUTES les lignes suivantes echouent,
        y compris les valides.
        """
        await self.db.rollback()

    async def delete(self, debiteur: Debiteur) -> None:
        await self.db.delete(debiteur)
        await self.db.commit()

    async def count(self, organisation_id: int | None) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(Debiteur).where(self._portee(organisation_id))
        )
        return result.scalar_one()

    # ---------- Faits du debiteur ----------
    #
    # Colonnes nues plutot que six GROUP BY : un debiteur porte des dizaines de
    # factures, pas des millions, et les regroupements se calculent alors sur le
    # meme instantane. Deux requetes separees pourraient se contredire si un
    # paiement s'enregistre entre les deux.

    async def lignes_creances(self, debiteur_id: int) -> list[tuple]:
        result = await self.db.execute(
            select(
                Creance.id,
                Creance.reference,
                Creance.montant_restant,
                Creance.date_echeance,
                Creance.date_saisie,
                Creance.statut,
            ).where(Creance.debiteur_id == debiteur_id)
        )
        return list(result.all())

    async def compter_relances(self, debiteur_id: int) -> list[tuple]:
        """Relances par canal, et combien ont obtenu un retour.

        « Avec reponse » se lit sur le champ resultat : il n'est rempli que
        lorsque le debiteur a effectivement reagi. C'est la seule trace de
        reponse dont dispose le modele de donnees.
        """
        result = await self.db.execute(
            select(
                Relance.type_relance,
                func.count().label("nb"),
                func.count(Relance.resultat).label("avec_reponse"),
            )
            .where(Relance.debiteur_id == debiteur_id)
            .group_by(Relance.type_relance)
        )
        return list(result.all())

    async def compter_promesses(self, debiteur_id: int) -> list[tuple]:
        result = await self.db.execute(
            select(Promesse.statut, func.count().label("nb"))
            .where(Promesse.debiteur_id == debiteur_id)
            .group_by(Promesse.statut)
        )
        return list(result.all())

    async def dates_solde(self, creance_ids: list[int]) -> dict[int, date]:
        """Dernier encaissement de chaque facture : le jour ou elle a ete soldee."""
        if not creance_ids:
            return {}
        result = await self.db.execute(
            select(Paiement.creance_id, func.max(Paiement.date_paiement))
            .where(Paiement.creance_id.in_(creance_ids))
            .group_by(Paiement.creance_id)
        )
        return dict(result.all())
