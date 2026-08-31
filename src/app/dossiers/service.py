from datetime import date
from decimal import Decimal

from app.clients.service import ClientService
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.creanciers.service import CreancierService
from app.dossiers.models import Dossier, StatutDossier
from app.dossiers.repository import DossierRepository
from app.dossiers.schemas import (
    ActionDossier,
    AnalyseDossier,
    DossierCreate,
    DossierListItem,
    DossierUpdate,
    EncoursDebiteur,
    FaitsDossier,
    LecturesGraphiques,
    concordance,
)
from app.ia.dossier import AnalyseDossierIA
from app.users.models import User


class DossierService:
    def __init__(
        self,
        repository: DossierRepository,
        client_service: ClientService,
        creancier_service: CreancierService,
        current_user: User,
    ) -> None:
        self.repository = repository
        self.client_service = client_service
        self.creancier_service = creancier_service
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_dossier(self, data: DossierCreate) -> Dossier:
        organisation_id = self._writable_organisation_id()
        await self.client_service.get_client(data.client_id)  # 404 hors organisation
        if data.creancier_id is not None:
            await self.creancier_service.get_creancier(data.creancier_id)
        # La reference vient du client : on ne la genere pas, on verifie juste
        # qu'elle ne fait pas doublon quand elle est fournie.
        if data.reference and await self.repository.get_by_reference(data.reference, organisation_id):
            raise ConflictException(f"Un dossier porte deja la reference « {data.reference} »")
        return await self.repository.create(data, organisation_id)

    async def get_dossier(self, dossier_id: int) -> Dossier:
        dossier = await self.repository.get_by_id(dossier_id)
        if dossier is None or (
            self.current_user.organisation_id is not None
            and dossier.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Dossier {dossier_id} introuvable")
        return dossier

    async def list_dossiers(
        self,
        skip: int = 0,
        limit: int = 100,
        client_id: int | None = None,
        creancier_id: int | None = None,
        statut: StatutDossier | None = None,
    ) -> list[DossierListItem]:
        lignes = await self.repository.list_enrichis(
            skip=skip,
            limit=limit,
            client_id=client_id,
            creancier_id=creancier_id,
            statut=statut,
            organisation_id=self.current_user.organisation_id,
        )
        items: list[DossierListItem] = []
        for dossier, client_nom, creancier_nom, nb, nb_deb, initial, restant in lignes:
            items.append(
                DossierListItem(
                    **{c.name: getattr(dossier, c.name) for c in dossier.__table__.columns},
                    client_nom=client_nom,
                    # Creancier vide = c'est le client lui-meme : on affiche son nom
                    # plutot qu'un tiret, l'information est la meme.
                    creancier_nom=creancier_nom or client_nom,
                    creancier_est_client=creancier_nom is None,
                    nb_creances=nb,
                    nb_debiteurs=nb_deb,
                    montant_initial=initial,
                    montant_restant=restant,
                    # Compare a l'initial et non au restant : l'annonce porte sur
                    # ce qui est confie, un encaissement ne la contredit pas.
                    concordance=concordance(dossier.montant_annonce, initial),
                )
            )
        return items

    async def update_dossier(self, dossier_id: int, data: DossierUpdate) -> Dossier:
        dossier = await self.get_dossier(dossier_id)
        organisation_id = self._writable_organisation_id()
        if data.client_id is not None:
            await self.client_service.get_client(data.client_id)
        if data.creancier_id is not None:
            await self.creancier_service.get_creancier(data.creancier_id)
        if data.reference and data.reference != dossier.reference:
            if await self.repository.get_by_reference(data.reference, organisation_id):
                raise ConflictException(f"Un dossier porte deja la reference « {data.reference} »")
        return await self.repository.update(dossier, data)

    async def delete_dossier(self, dossier_id: int) -> None:
        dossier = await self.get_dossier(dossier_id)
        self._writable_organisation_id()
        # Supprimer un dossier ne doit jamais faire disparaitre des impayes. Le
        # comptage passe par le repository : dossier.creances est une relation
        # lazy, y toucher ici leverait MissingGreenlet en session async.
        if await self.repository.compter_creances(dossier.id) > 0:
            raise BadRequestException(
                "Ce dossier porte des creances : supprimez-les d'abord"
            )
        await self.repository.delete(dossier)

    async def faits_dossier(self, dossier_id: int) -> FaitsDossier:
        """L'etat chiffre du dossier, calcule ici et nulle part ailleurs.

        Les bornes de tranches sont celles de la balance agee du portefeuille
        (« non-echu », « 1-30 »…) : deux decoupages differents pour la meme notion
        finiraient par se contredire d'un ecran a l'autre.
        """
        dossier = await self.get_dossier(dossier_id)
        client = await self.client_service.get_client(dossier.client_id)
        creancier = (
            await self.creancier_service.get_creancier(dossier.creancier_id)
            if dossier.creancier_id is not None
            else None
        )

        lignes = await self.repository.lignes_creances(dossier_id)
        noms = await self.repository.noms_debiteurs(dossier_id)
        aujourdhui = date.today()

        confie = sum((ligne[1] for ligne in lignes), Decimal(0))
        restant = sum((ligne[2] for ligne in lignes), Decimal(0))

        par_statut: dict[str, int] = {}
        balance: dict[str, Decimal] = {}
        par_debiteur: dict[int, dict] = {}

        for debiteur_id, initial, reste, echeance, statut in lignes:
            # Le retard se deduit de la date, jamais du statut stocke : EN_RETARD
            # n'est ecrit nulle part, c'est la regle du reste de l'application.
            jours = (aujourdhui - echeance).days
            effectif = (
                "EN_RETARD" if statut.value == "EN_COURS" and jours > 0 else statut.value
            )
            par_statut[effectif] = par_statut.get(effectif, 0) + 1

            if statut.value not in ("SOLDEE", "ANNULEE"):
                tranche = (
                    "non-echu" if jours <= 0
                    else "1-30" if jours <= 30
                    else "31-60" if jours <= 60
                    else "61-90" if jours <= 90
                    else "90+"
                )
                balance[tranche] = balance.get(tranche, Decimal(0)) + reste

            agrege = par_debiteur.setdefault(
                debiteur_id, {"nb": 0, "restant": Decimal(0), "retard": 0}
            )
            agrege["nb"] += 1
            agrege["restant"] += reste
            agrege["retard"] = max(agrege["retard"], jours)

        relances_par_canal: dict[str, int] = {}
        echouees = 0
        for canal, statut_relance, nb in await self.repository.compter_relances(dossier_id):
            relances_par_canal[canal.value] = relances_par_canal.get(canal.value, 0) + nb
            if statut_relance.value == "ECHOUEE":
                echouees += nb

        promesses: dict[str, int] = {}
        rompues_par_debiteur: dict[int, int] = {}
        for debiteur_id, statut_promesse, nb, _ in await self.repository.compter_promesses(dossier_id):
            promesses[statut_promesse.value] = promesses.get(statut_promesse.value, 0) + nb
            if statut_promesse.value == "ROMPUE":
                rompues_par_debiteur[debiteur_id] = rompues_par_debiteur.get(debiteur_id, 0) + nb

        relance_par_debiteur = dict(await self.repository.derniere_relance_par_debiteur(dossier_id))

        debiteurs = sorted(
            (
                EncoursDebiteur(
                    nom=noms.get(debiteur_id, f"Debiteur {debiteur_id}"),
                    nb_creances=a["nb"],
                    montant_restant=a["restant"],
                    retard_max_jours=a["retard"],
                    promesses_rompues=rompues_par_debiteur.get(debiteur_id, 0),
                    derniere_relance=relance_par_debiteur.get(debiteur_id),
                )
                for debiteur_id, a in par_debiteur.items()
            ),
            key=lambda d: d.montant_restant,
            reverse=True,
        )

        encaisse = confie - restant
        return FaitsDossier(
            reference=dossier.reference,
            client=client.nom,
            creancier=creancier.nom if creancier else client.nom,
            type_dossier=dossier.type_dossier,
            objectif=dossier.objectif,
            statut=dossier.statut,
            date_reception=dossier.date_reception,
            anciennete_jours=(aujourdhui - dossier.date_reception).days,
            nb_creances=len(lignes),
            nb_debiteurs=len(par_debiteur),
            montant_confie=confie,
            montant_restant=restant,
            montant_encaisse=encaisse,
            taux_recouvrement=int(encaisse / confie * 100) if confie > 0 else 0,
            montant_annonce=dossier.montant_annonce,
            ecart_annonce=(dossier.montant_annonce - confie) if dossier.montant_annonce is not None else None,
            concordance=concordance(dossier.montant_annonce, confie),
            creances_par_statut=par_statut,
            balance_agee=balance,
            debiteurs=debiteurs,
            relances_par_canal=relances_par_canal,
            relances_echouees=echouees,
            derniere_relance=max(relance_par_debiteur.values(), default=None),
            promesses=promesses,
        )

    async def analyser_dossier(self, dossier_id: int, analyse_ia: AnalyseDossierIA) -> AnalyseDossier:
        """Passe payante : un appel de modele, declenche a la demande.

        Les faits accompagnent l'analyse dans la reponse. Sans eux, l'agent lirait
        un avis sans pouvoir en verifier l'assise — or chaque action cite un
        chiffre qui doit etre confrontable.
        """
        faits = await self.faits_dossier(dossier_id)
        synthese, actions, lectures, modele = await analyse_ia.analyser(faits)
        return AnalyseDossier(
            synthese=synthese,
            actions=[ActionDossier(**a) for a in actions],
            lectures=LecturesGraphiques(**lectures),
            faits=faits,
            modele=modele,
        )
