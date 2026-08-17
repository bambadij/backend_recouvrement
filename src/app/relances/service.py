from datetime import date
from decimal import Decimal

from app.core.exceptions import ForbiddenException, NotFoundException
from app.debiteurs.service import DebiteurService
from app.dossiers.service import DossierService
from app.relances.models import Relance, StatutRelance
from app.relances.repository import RelanceRepository
from app.relances.schemas import (
    FileDeTravail,
    FileDisponible,
    LigneARelancer,
    RelanceCreate,
    RelanceUpdate,
)
from app.users.models import User


class RelanceService:
    #: Au-dela de ce retard, une dette n'est plus un simple oubli de paiement.
    RETARD_JOURS = 30
    #: Delai sans reponse au-dela duquel une relance restee lettre morte doit
    #: etre reprise, en general sur un autre canal.
    SILENCE_JOURS = 15
    #: Part du portefeuille que retient la file « les plus gros montants ».
    #:
    #: Un seuil fixe en francs ne tient pas : essaye a 500 000 F sur le
    #: portefeuille reel, il retenait les huit lignes sur huit — un filtre qui
    #: ne filtre rien. Une part se recalibre d'elle-meme, quelle que soit la
    #: taille des dossiers d'une organisation.
    PART_GROS_MONTANTS = 0.2

    #: L'ordre compte : la premiere file est celle qu'on ouvre par defaut.
    _LIBELLES = {
        "retard": f"Retard > {RETARD_JOURS} j",
        "jamais_relance": "Jamais relancés",
        "sans_reponse": f"Sans réponse depuis {SILENCE_JOURS} j",
        "gros_montant": "Les plus gros montants",
    }

    def __init__(
        self,
        repository: RelanceRepository,
        dossier_service: DossierService,
        debiteur_service: DebiteurService,
        current_user: User,
    ) -> None:
        self.repository = repository
        self.dossier_service = dossier_service
        self.debiteur_service = debiteur_service
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException("Un super-administrateur ne gere pas directement les donnees d'une organisation")
        return self.current_user.organisation_id

    async def create_relance(self, data: RelanceCreate) -> Relance:
        organisation_id = self._writable_organisation_id()
        await self.dossier_service.get_dossier(data.dossier_id)  # 404 si dossier d'une autre organisation
        await self.debiteur_service.get_debiteur(data.debiteur_id)
        agent = f"{self.current_user.prenom} {self.current_user.nom}".strip() or None
        return await self.repository.create(data, organisation_id, cree_par_nom=agent)

    async def get_relance(self, relance_id: int) -> Relance:
        relance = await self.repository.get_by_id(relance_id)
        if relance is None or (
            self.current_user.organisation_id is not None
            and relance.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Relance {relance_id} introuvable")
        return relance

    async def list_relances(
        self,
        skip: int = 0,
        limit: int = 100,
        dossier_id: int | None = None,
        debiteur_id: int | None = None,
        statut: StatutRelance | None = None,
        avec_resultat: bool | None = None,
    ) -> list[Relance]:
        return await self.repository.list(
            skip=skip,
            limit=limit,
            dossier_id=dossier_id,
            debiteur_id=debiteur_id,
            organisation_id=self.current_user.organisation_id,
            statut=statut,
            avec_resultat=avec_resultat,
        )

    async def file_de_travail(self, file: str | None = None, limit: int = 100) -> FileDeTravail:
        """La file de travail du jour : par quoi commencer, et pourquoi.

        Quatre criteres, tous calcules sur le meme jeu de lignes. Ils se
        recouvrent volontairement — une grosse dette jamais relancee apparait
        dans deux files : ce sont des points de vue sur le meme portefeuille,
        pas des categories exclusives.

        Rien n'est envoye ici. L'application ne dispose d'aucun moyen
        d'expedition : la file amene l'agent sur la creance, il redige avec
        l'assistant, envoie depuis son propre outil, puis marque la relance
        partie.
        """
        organisation_id = self.current_user.organisation_id
        couples = await self.repository.couples_a_relancer(organisation_id)
        dernieres = await self.repository.derniere_relance_envoyee(organisation_id)
        planifiees = await self.repository.relances_planifiees(organisation_id)
        aujourdhui = date.today()

        lignes: list[LigneARelancer] = []
        for couple in couples:
            cle = (couple.dossier_id, couple.debiteur_id)
            derniere = dernieres.get(cle)
            repondue = bool(derniere is not None and (derniere.resultat or "").strip())
            ligne = LigneARelancer(
                dossier_id=couple.dossier_id,
                dossier_reference=couple.dossier_reference,
                debiteur_id=couple.debiteur_id,
                debiteur_nom=f"{couple.prenom} {couple.nom}".strip() or (couple.entreprise or ""),
                debiteur_entreprise=couple.entreprise,
                nb_factures=couple.nb_factures,
                montant_restant=Decimal(couple.montant_restant),
                jours_retard=(aujourdhui - couple.plus_ancienne_echeance).days,
                creance_id=couple.creance_ids[0],
                derniere_relance=derniere.date_relance if derniere else None,
                derniere_relance_canal=derniere.type_relance if derniere else None,
                derniere_relance_repondue=repondue,
                relance_planifiee_id=planifiees.get(cle),
            )
            lignes.append(ligne)

        seuil = self._seuil_gros_montants(lignes)
        appartenances = [self._files_de(ligne, aujourdhui, seuil) for ligne in lignes]

        files = [
            FileDisponible(
                cle=cle,
                libelle=libelle,
                effectif=sum(1 for f in appartenances if cle in f),
            )
            for cle, libelle in self._LIBELLES.items()
        ]

        active = file if file in self._LIBELLES else next(iter(self._LIBELLES))
        # Les plus gros montants d'abord : a temps de traitement egal, c'est la
        # ou l'heure de l'agent rapporte le plus.
        retenues = sorted(
            (ligne for ligne, f in zip(lignes, appartenances) if active in f),
            key=lambda ligne: ligne.montant_restant,
            reverse=True,
        )
        return FileDeTravail(file_active=active, files=files, lignes=retenues[:limit])

    def _seuil_gros_montants(self, lignes: list[LigneARelancer]) -> Decimal | None:
        """Montant a partir duquel une ligne compte parmi « les plus gros ».

        None quand il n'y a rien a trier : la file est alors vide, plutot que de
        retenir par defaut l'unique ligne d'un portefeuille de une.
        """
        if len(lignes) < 2:
            return None
        montants = sorted((ligne.montant_restant for ligne in lignes), reverse=True)
        # Au moins une ligne des qu'il y en a deux : un arrondi a zero viderait
        # la file sur les petits portefeuilles.
        rang = max(1, round(len(montants) * self.PART_GROS_MONTANTS)) - 1
        return montants[rang]

    def _files_de(
        self, ligne: LigneARelancer, aujourdhui: date, seuil_montant: Decimal | None
    ) -> set[str]:
        """Les criteres auxquels une ligne repond."""
        files = set()
        if ligne.jours_retard > self.RETARD_JOURS:
            files.add("retard")
        # « Jamais relance » se lit sur les relances PARTIES, mais une relance
        # deja planifiee exclut la ligne : le travail est fait, il attend
        # seulement d'etre marque.
        if ligne.derniere_relance is None and ligne.relance_planifiee_id is None:
            files.add("jamais_relance")
        if (
            ligne.derniere_relance is not None
            and not ligne.derniere_relance_repondue
            and (aujourdhui - ligne.derniere_relance).days > self.SILENCE_JOURS
        ):
            files.add("sans_reponse")
        if seuil_montant is not None and ligne.montant_restant >= seuil_montant:
            files.add("gros_montant")
        return files

    async def update_relance(self, relance_id: int, data: RelanceUpdate) -> Relance:
        relance = await self.get_relance(relance_id)
        self._writable_organisation_id()
        return await self.repository.update(relance, data)

    async def delete_relance(self, relance_id: int) -> None:
        relance = await self.get_relance(relance_id)
        self._writable_organisation_id()
        await self.repository.delete(relance)
