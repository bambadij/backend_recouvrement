from decimal import Decimal

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.debiteurs.models import Debiteur
from app.debiteurs.repository import DebiteurRepository
from app.debiteurs.schemas import (
    CanalDebiteur,
    DebiteurCreate,
    DebiteurUpdate,
    DelaiReglement,
    FaitsDebiteur,
)
from app.users.models import User


class DebiteurService:
    def __init__(self, repository: DebiteurRepository, current_user: User) -> None:
        self.repository = repository
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_debiteur(self, data: DebiteurCreate) -> Debiteur:
        organisation_id = self._writable_organisation_id()
        if data.email and await self.repository.get_by_email(data.email, organisation_id):
            raise ConflictException(f"Un debiteur avec l'email {data.email} existe deja")
        return await self.repository.create(data, organisation_id)

    async def get_debiteur(self, debiteur_id: int) -> Debiteur:
        debiteur = await self.repository.get_by_id(debiteur_id)
        if debiteur is None or (
            self.current_user.organisation_id is not None
            and debiteur.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Debiteur {debiteur_id} introuvable")
        return debiteur

    async def list_debiteurs(self, skip: int = 0, limit: int = 100, search: str | None = None) -> list[Debiteur]:
        return await self.repository.list(
            skip=skip, limit=limit, search=search, organisation_id=self.current_user.organisation_id
        )

    async def update_debiteur(self, debiteur_id: int, data: DebiteurUpdate) -> Debiteur:
        debiteur = await self.get_debiteur(debiteur_id)
        self._writable_organisation_id()
        if data.email and data.email != debiteur.email:
            existing = await self.repository.get_by_email(data.email, debiteur.organisation_id)
            if existing is not None:
                raise ConflictException(f"Un debiteur avec l'email {data.email} existe deja")
        return await self.repository.update(debiteur, data)

    async def delete_debiteur(self, debiteur_id: int) -> None:
        debiteur = await self.get_debiteur(debiteur_id)
        self._writable_organisation_id()
        await self.repository.delete(debiteur)

    async def faits_debiteur(self, debiteur_id: int) -> FaitsDebiteur:
        """L'etat chiffre du debiteur, calcule ici et nulle part ailleurs.

        Situe une facture dans l'histoire de celui qui la doit : la page de
        detail n'en montre qu'une, alors que le choix du canal, du ton et de
        l'echeancier se prend au vu de son comportement d'ensemble.
        """
        debiteur = await self.get_debiteur(debiteur_id)
        lignes = await self.repository.lignes_creances(debiteur_id)

        soldees = [ligne for ligne in lignes if ligne[5].value == "SOLDEE"]
        dates_solde = await self.repository.dates_solde([ligne[0] for ligne in soldees])

        delais = []
        for creance_id, reference, _restant, echeance, _saisie, _statut in soldees:
            date_solde = dates_solde.get(creance_id)
            # Une facture soldee sans aucun paiement enregistre existe : statut
            # bascule a la main, remise gracieuse, ecriture passee ailleurs. On
            # ne peut pas en tirer de delai, on la laisse de cote plutot que
            # d'inventer une date.
            if date_solde is None:
                continue
            delais.append(
                DelaiReglement(
                    reference=reference,
                    date_echeance=echeance,
                    date_solde=date_solde,
                    jours=(date_solde - echeance).days,
                )
            )
        delais.sort(key=lambda d: d.date_solde)

        canaux = []
        reponses = 0
        for canal, nb, avec_reponse in await self.repository.compter_relances(debiteur_id):
            reponses += avec_reponse
            canaux.append(
                CanalDebiteur(canal=canal.value, envoyees=nb, avec_reponse=avec_reponse)
            )
        canaux.sort(key=lambda c: c.envoyees, reverse=True)

        promesses = {
            statut.value: nb for statut, nb in await self.repository.compter_promesses(debiteur_id)
        }

        # Encours : les creances annulees ne sont plus dues, les soldees valent zero.
        encours = sum(
            (ligne[2] for ligne in lignes if ligne[5].value not in ("SOLDEE", "ANNULEE")),
            Decimal(0),
        )

        return FaitsDebiteur(
            nom=f"{debiteur.prenom} {debiteur.nom}".strip(),
            entreprise=debiteur.entreprise,
            premiere_creance=min((ligne[4] for ligne in lignes), default=None),
            nb_creances=len(lignes),
            nb_soldees=len(soldees),
            encours_total=encours,
            canaux=canaux,
            reponses_tracees=reponses > 0,
            delais=delais,
            promesses=promesses,
        )
