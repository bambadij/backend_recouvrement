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
from app.segmentation.models import RANG_POTENTIEL
from app.segmentation.repository import SegmentationRepository
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
        segmentation_repository: SegmentationRepository,
        current_user: User,
    ) -> None:
        self.repository = repository
        self.dossier_service = dossier_service
        self.debiteur_service = debiteur_service
        # Le depot, pas le service : on ne fait que LIRE un classement deja
        # calcule. Passer par le service de segmentation exposerait ici la passe
        # payante, dans un ecran ou personne ne doit pouvoir la declencher.
        self.segmentation_repository = segmentation_repository
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

    async def file_de_travail(
        self, file: str | None = None, limit: int = 100, tri: str | None = None
    ) -> FileDeTravail:
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
        # Le classement, quand il existe. Une lecture en base, aucun appel de
        # modele : la file s'affiche a la meme vitesse qu'avant.
        classement = await self.segmentation_repository.classement_par_couple(organisation_id)
        aujourdhui = date.today()

        lignes: list[LigneARelancer] = []
        for couple in couples:
            cle = (couple.dossier_id, couple.debiteur_id)
            derniere = dernieres.get(cle)
            repondue = bool(derniere is not None and (derniere.resultat or "").strip())
            classe = classement.get(cle)
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
                creance_reference=couple.creance_references[0],
                derniere_relance=derniere.date_relance if derniere else None,
                derniere_relance_canal=derniere.type_relance if derniere else None,
                derniere_relance_repondue=repondue,
                relance_planifiee_id=planifiees.get(cle),
                segment=classe[0].segment if classe else None,
                potentiel=classe[0].potentiel if classe else None,
                justification=classe[0].justification if classe else None,
                creance_classee_reference=classe[1].reference if classe else None,
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
        dans_la_file = [ligne for ligne, f in zip(lignes, appartenances) if active in f]

        # Le classement quand il existe, le montant sinon — ou sur demande. Un
        # ecran qui n'afficherait rien tant qu'aucune passe n'a tourne serait un
        # ecran de travail rendu inutilisable par une fonction facultative.
        classees = [ligne for ligne in dans_la_file if ligne.potentiel is not None]
        tri_actif = "montant" if tri == "montant" or not classees else "classement"

        if tri_actif == "classement":
            # Meme regle que la page de classement : d'abord ce qui a le plus de
            # chances d'aboutir, le montant tranchant a potentiel egal. Deux
            # ordres differents pour la meme question finiraient par se
            # contredire sous les yeux de l'agent.
            retenues = sorted(
                dans_la_file,
                key=lambda ligne: (
                    ligne.potentiel is None,
                    RANG_POTENTIEL.get(ligne.potentiel, 99),
                    -ligne.montant_restant,
                ),
            )
        else:
            # Les plus gros montants d'abord : a temps de traitement egal, c'est
            # la ou l'heure de l'agent rapporte le plus.
            retenues = sorted(dans_la_file, key=lambda ligne: ligne.montant_restant, reverse=True)

        return FileDeTravail(
            file_active=active,
            files=files,
            lignes=retenues[:limit],
            tri_actif=tri_actif,
            classement_calcule_le=max(
                (c[0].calcule_le for c in classement.values()), default=None
            ),
            non_classees=sum(1 for ligne in dans_la_file if ligne.potentiel is None),
        )

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
