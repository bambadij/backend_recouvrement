from datetime import date, timedelta
from decimal import Decimal

from app.core.exceptions import NotFoundException
from app.creances.repository import CreanceRepository
from app.debiteurs.repository import DebiteurRepository
from app.organisations.repository import OrganisationRepository
from app.organisations.schemas import (
    Alerte,
    ApercuOrganisation,
    CaseRisque,
    RecouvrementCompare,
    SerieRecouvrement,
    Efficacite,
    LigneClassement,
    LigneProductivite,
    MontantParMois,
    OrganisationStats,
    PointBalanceAgee,
    PrevisionMois,
    StatsPromesses,
    TrancheBalanceAgee,
)
from app.paiements.repository import PaiementRepository
from app.promesses.repository import PromesseRepository
from app.relances.repository import RelanceRepository
from app.segmentation.repository import SegmentationRepository
from app.users.repository import UserRepository


class OrganisationStatsService:
    def __init__(
        self,
        organisation_repository: OrganisationRepository,
        debiteur_repository: DebiteurRepository,
        creance_repository: CreanceRepository,
        paiement_repository: PaiementRepository,
        relance_repository: RelanceRepository,
        user_repository: UserRepository,
        segmentation_repository: SegmentationRepository,
        promesse_repository: PromesseRepository,
    ) -> None:
        self.organisation_repository = organisation_repository
        self.debiteur_repository = debiteur_repository
        self.creance_repository = creance_repository
        self.paiement_repository = paiement_repository
        self.relance_repository = relance_repository
        self.user_repository = user_repository
        self.segmentation_repository = segmentation_repository
        self.promesse_repository = promesse_repository

    #: Période glissante par défaut des indicateurs d'efficacité. Un trimestre :
    #: assez long pour absorber la saisonnalité des encaissements, assez court
    #: pour rester actuel. L'appelant peut la surcharger.
    PERIODE_EFFICACITE_JOURS = 90

    #: Profondeur de l'historique de balance âgée, en fins de mois.
    HISTORIQUE_MOIS = 6

    #: Horizon du calendrier des échéances à venir.
    HORIZON_MOIS = 6

    TOP_DEBITEURS = 5

    #: Au-dela de ce silence, un dossier actif remonte en alerte.
    SILENCE_ALERTE_JOURS = 30

    #: Un dossier critique au-dessus de ce montant merite une alerte nominative.
    MONTANT_ALERTE = Decimal("1000000")

    #: Coefficients de ponderation des echeances a venir, par potentiel de
    #: recouvrement. CONVENTIONNELS, non calibres : aucun historique de dossiers
    #: reellement recouvres ne permet aujourd'hui de les estimer. Ils traduisent un
    #: ordre — un dossier a fort potentiel rentre plus souvent qu'un dossier a
    #: faible potentiel — pas une probabilite mesuree. A revoir des qu'un an de
    #: donnees permettra de les ajuster.
    POIDS_POTENTIEL = {"FORT": Decimal("0.8"), "MOYEN": Decimal("0.5"), "FAIBLE": Decimal("0.2")}

    @staticmethod
    def calculer_dso(encours: Decimal, flux: Decimal, periode_jours: int) -> int | None:
        """DSO = encours / flux confie x duree de la fenetre, arrondi au jour.

        Renvoie None quand le flux est nul : le ratio n'est pas defini, et un 0
        se lirait comme « tout encaisse le jour meme », soit l'inverse de
        « rien a mesurer ». Publique et pure pour etre testable seule — c'est le
        seul endroit du service ou une formule est appliquee.
        """
        if flux <= 0:
            return None
        return int(round(encours / flux * periode_jours))

    @staticmethod
    def calculer_cei(
        encours_debut: Decimal, flux: Decimal, encours_fin: Decimal, non_echu_fin: Decimal
    ) -> int | None:
        """Collection Effectiveness Index, en pourcentage.

        CEI = (encours debut + flux confie - encours fin) /
              (encours debut + flux confie - encours fin NON ECHU) x 100

        Le numerateur est ce qui a ete encaisse ; le denominateur, ce qui pouvait
        l'etre — car ce qui n'est pas encore echu ne pouvait de toute facon pas
        etre recouvre sur la periode. Le ratio est donc borne a 100 % dans un
        fonctionnement normal.

        Renvoie None quand le denominateur est nul ou negatif : il n'y avait rien
        a recouvrer, et un 0 % se lirait comme un echec.
        """
        recouvrable = encours_debut + flux - non_echu_fin
        if recouvrable <= 0:
            return None
        encaisse = encours_debut + flux - encours_fin
        return int(round(encaisse / recouvrable * 100))

    @staticmethod
    def _fins_de_mois(nb_mois: int) -> list[date]:
        """Dernier jour de chacun des nb_mois derniers mois, le plus ancien d'abord.

        Le dernier point est aujourd'hui et non la fin du mois courant : sinon il
        porterait sur un futur qui n'a pas encore été encaissé.
        """
        aujourdhui = date.today()
        points: list[date] = []
        premier_du_mois = aujourdhui.replace(day=1)
        for _ in range(nb_mois - 1):
            premier_du_mois = (premier_du_mois - timedelta(days=1)).replace(day=1)
        for _ in range(nb_mois - 1):
            suivant = (premier_du_mois + timedelta(days=32)).replace(day=1)
            points.append(suivant - timedelta(days=1))
            premier_du_mois = suivant
        points.append(aujourdhui)
        return points

    async def apercu_organisations(self) -> list[ApercuOrganisation]:
        """Comparatif de toutes les organisations, sans selection prealable.

        Trois requetes au total, quel que soit le nombre d'organisations : la liste,
        un GROUP BY sur les creances, un GROUP BY sur les utilisateurs.
        """
        organisations = await self.organisation_repository.list(limit=500)
        creances = await self.creance_repository.resume_par_organisation()
        utilisateurs = await self.user_repository.count_par_organisation()

        lignes: list[ApercuOrganisation] = []
        for org in organisations:
            nb_creances, initial, restant, restant_90 = creances.get(
                org.id, (0, Decimal("0"), Decimal("0"), Decimal("0"))
            )
            lignes.append(
                ApercuOrganisation(
                    organisation_id=org.id,
                    nom=org.nom,
                    nb_utilisateurs=utilisateurs.get(org.id, 0),
                    nb_creances=nb_creances,
                    montant_restant=restant,
                    taux_recouvrement=(
                        int(round((initial - restant) / initial * 100)) if initial > 0 else None
                    ),
                    part_plus_90j=(
                        int(round(restant_90 / restant * 100)) if restant > 0 else None
                    ),
                )
            )
        # Du plus gros encours au plus petit : c'est l'ordre dans lequel on arbitre.
        lignes.sort(key=lambda ligne: ligne.montant_restant, reverse=True)
        return lignes

    async def recouvrement_compare(self, nb_mois: int = 6) -> RecouvrementCompare:
        """Encaissements mois par mois, une serie par organisation.

        Deux requetes : la liste des organisations, et un GROUP BY sur les paiements.
        """
        organisations = await self.organisation_repository.list(limit=500)
        lignes = await self.paiement_repository.recouvrement_par_organisation_et_mois(nb_mois)

        # Axe commun : les nb_mois mois calendaires jusqu'au mois courant inclus.
        aujourdhui = date.today().replace(day=1)
        mois: list[str] = []
        curseur = aujourdhui
        for _ in range(nb_mois - 1):
            curseur = (curseur - timedelta(days=1)).replace(day=1)
        for _ in range(nb_mois):
            mois.append(curseur.strftime("%Y-%m"))
            curseur = (curseur + timedelta(days=32)).replace(day=1)

        par_org: dict[int, dict[str, Decimal]] = {}
        for org_id, m, montant in lignes:
            par_org.setdefault(org_id, {})[m] = montant

        series = [
            SerieRecouvrement(
                organisation_id=org.id,
                nom=org.nom,
                # Zero explicite sur les mois sans encaissement : une barre manquante
                # et une barre a zero ne se lisent pas de la meme facon.
                montants={m: par_org.get(org.id, {}).get(m, Decimal("0")) for m in mois},
            )
            for org in organisations
        ]
        return RecouvrementCompare(mois=mois, series=series)

    def _coefficient_moyen(self, cartographie: list[CaseRisque]) -> Decimal:
        """Poids moyen du portefeuille, pondéré par les montants de chaque case.

        Les échéances à venir ne sont disponibles qu'agrégées par mois, sans
        ventilation par dossier : on ne peut donc pas pondérer créance par
        créance. On applique le poids moyen du portefeuille classé — approximation
        assumée, et elle vaut ce que valent les coefficients ci-dessus.
        """
        total = sum((c.montant for c in cartographie), Decimal(0))
        if total <= 0:
            return self.POIDS_POTENTIEL["MOYEN"]
        pondere = sum(
            (c.montant * self.POIDS_POTENTIEL.get(c.potentiel, Decimal("0.5")) for c in cartographie),
            Decimal(0),
        )
        return pondere / total

    def _previsions(
        self,
        engagements: dict[str, Decimal],
        echeances: dict[str, Decimal],
        coefficient: Decimal,
    ) -> list[PrevisionMois]:
        """Fusionne engagements datés et échéances pondérées sur un axe de mois commun."""
        mois = sorted(set(engagements) | set(echeances))
        previsions = []
        for m in mois:
            engage = engagements.get(m, Decimal(0))
            pondere = (echeances.get(m, Decimal(0)) * coefficient).quantize(Decimal("1"))
            previsions.append(
                PrevisionMois(mois=m, engage=engage, pondere=pondere, total=engage + pondere)
            )
        return previsions

    def _alertes(
        self,
        promesses_rompues: int,
        silencieux: list[tuple[int, str, Decimal, int, bool]],
        cartographie: list[CaseRisque],
        balance: dict[str, tuple[Decimal, int]],
    ) -> list[Alerte]:
        """Règles déterministes. Aucun modèle n'intervient ici : une alerte doit
        pouvoir être refaite à la main par l'agent qui la reçoit."""
        alertes: list[Alerte] = []

        if promesses_rompues:
            alertes.append(
                Alerte(
                    code="promesses_rompues",
                    severite="critique",
                    titre=f"{promesses_rompues} promesse(s) non tenue(s)",
                    detail=(
                        "L'échéance promise est passée sans encaissement suffisant. "
                        "Un engagement rompu est le signal le plus prédictif d'un dossier qui dérive."
                    ),
                )
            )

        montant_90, nb_90 = balance.get("90+", (Decimal(0), 0))
        if nb_90:
            alertes.append(
                Alerte(
                    code="encours_90j",
                    severite="critique",
                    titre=f"{nb_90} dossier(s) à plus de 90 jours",
                    detail="Au-delà de 90 jours, la probabilité de recouvrement amiable chute nettement.",
                    montant=montant_90,
                )
            )

        # Les plus gros dossiers muets d'abord : c'est là que le silence coûte cher.
        for creance_id, reference, montant, jours, jamais in sorted(
            silencieux, key=lambda x: x[2], reverse=True
        )[:5]:
            titre = (
                f"{reference} échue depuis {jours} jours, jamais relancée"
                if jamais
                else f"{reference} sans relance depuis {jours} jours"
            )
            alertes.append(
                Alerte(
                    code="jamais_relancee" if jamais else "sans_relance",
                    severite="attention",
                    titre=titre,
                    detail=f"Dossier actif de {montant:,.0f} FCFA laissé sans action.".replace(",", " "),
                    creance_id=creance_id,
                    reference=reference,
                    montant=montant,
                )
            )

        critiques = [c for c in cartographie if c.segment == "CRITIQUE"]
        montant_critique = sum((c.montant for c in critiques), Decimal(0))
        if montant_critique >= self.MONTANT_ALERTE:
            nb = sum(c.nb_creances for c in critiques)
            alertes.append(
                Alerte(
                    code="encours_critique",
                    severite="critique",
                    titre=f"{montant_critique:,.0f} FCFA classés critiques".replace(",", " "),
                    detail=f"Répartis sur {nb} dossier(s). À arbitrer : relance ferme ou passage au judiciaire.",
                    montant=montant_critique,
                )
            )

        return alertes

    async def get_stats(
        self, organisation_id: int | None, periode_jours: int | None = None
    ) -> OrganisationStats:
        """Statistiques d'une organisation, ou du parc entier si organisation_id est None.

        La vue plateforme somme les encours de toutes les organisations. C'est valide
        tant que l'application est mono-devise : tous les montants sont en FCFA. Le jour
        ou la devise devient un attribut de la creance, cette agregation devra etre
        ventilee par devise — sommer des euros et des francs n'aurait plus de sens.
        """
        # Rien a verifier sur la vue plateforme : elle ne cible aucune organisation.
        if organisation_id is not None:
            if await self.organisation_repository.get_by_id(organisation_id) is None:
                raise NotFoundException(f"Organisation {organisation_id} introuvable")

        nb_debiteurs = await self.debiteur_repository.count(organisation_id)
        creances_par_statut = await self.creance_repository.count_by_statut(organisation_id)
        montant_total_initial, montant_total_restant = await self.creance_repository.sum_montants(organisation_id)
        nb_paiements, montant_total_encaisse = await self.paiement_repository.stats(organisation_id)
        nb_relances = await self.relance_repository.count(organisation_id)
        nb_utilisateurs = await self.user_repository.count(organisation_id)
        balance = await self.creance_repository.balance_agee(organisation_id)

        periode = periode_jours or self.PERIODE_EFFICACITE_JOURS
        encours, flux = await self.creance_repository.encours_et_flux(organisation_id, periode)
        delai_moyen = await self.paiement_repository.delai_moyen_encaissement(organisation_id, periode)
        dso = self.calculer_dso(encours, flux, periode)

        historique = [
            PointBalanceAgee(
                date_ref=jour,
                tranches=await self.creance_repository.balance_agee_a_date(organisation_id, jour),
            )
            for jour in self._fins_de_mois(self.HISTORIQUE_MOIS)
        ]
        echeances = await self.creance_repository.echeances_a_venir(organisation_id, self.HORIZON_MOIS)
        debiteurs = await self.creance_repository.top_debiteurs(organisation_id, self.TOP_DEBITEURS)
        encaisseurs = await self.paiement_repository.encaissements_par_utilisateur(organisation_id, periode)

        # CEI : la photo de depart est celle d'il y a `periode` jours ; la photo
        # d'arrivee est celle d'aujourd'hui, dont on isole la part non echue.
        debut = date.today() - timedelta(days=periode)
        tranches_debut = await self.creance_repository.balance_agee_a_date(organisation_id, debut)
        encours_debut = sum(tranches_debut.values(), Decimal(0))
        non_echu_fin = balance.get("non-echu", (Decimal(0), 0))[0]
        cei = self.calculer_cei(encours_debut, flux, montant_total_restant, non_echu_fin)

        cartographie = [
            CaseRisque(segment=s, potentiel=p, nb_creances=nb, montant=montant)
            for s, p, nb, montant in await self.segmentation_repository.cartographie(organisation_id)
        ]

        par_statut, montant_attendu = await self.promesse_repository.statistiques(organisation_id)
        controlees = (
            par_statut.get("TENUE", 0) + par_statut.get("PARTIELLE", 0) + par_statut.get("ROMPUE", 0)
        )
        promesses = StatsPromesses(
            nb_attendues=par_statut.get("ATTENDUE", 0),
            nb_tenues=par_statut.get("TENUE", 0),
            nb_partielles=par_statut.get("PARTIELLE", 0),
            nb_rompues=par_statut.get("ROMPUE", 0),
            montant_attendu=montant_attendu,
            taux_tenue=(
                int(round(par_statut.get("TENUE", 0) / controlees * 100)) if controlees else None
            ),
        )

        engagements = await self.promesse_repository.engagements_par_mois(organisation_id)
        previsions = self._previsions(engagements, echeances, self._coefficient_moyen(cartographie))

        activite = await self.relance_repository.activite_par_agent(organisation_id)
        promesses_agent = await self.promesse_repository.obtenues_par_agent(organisation_id)
        encaisse_agent = {nom: (montant, nb) for nom, montant, nb in encaisseurs}
        productivite = [
            LigneProductivite(
                agent=agent,
                relances_emises=activite.get(agent, (0, 0))[0],
                relances_avec_retour=activite.get(agent, (0, 0))[1],
                promesses_obtenues=promesses_agent.get(agent, (0, 0))[0],
                promesses_tenues=promesses_agent.get(agent, (0, 0))[1],
                nb_paiements=encaisse_agent.get(agent, (Decimal(0), 0))[1],
                montant_encaisse=encaisse_agent.get(agent, (Decimal(0), 0))[0],
            )
            # Union des trois sources : un agent qui relance sans encaisser doit
            # apparaitre, et reciproquement.
            for agent in sorted(set(activite) | set(promesses_agent) | set(encaisse_agent))
        ]

        silencieux = await self.relance_repository.creances_sans_relance_depuis(
            organisation_id, self.SILENCE_ALERTE_JOURS
        )
        alertes = self._alertes(promesses.nb_rompues, silencieux, cartographie, balance)

        return OrganisationStats(
            organisation_id=organisation_id,
            nb_debiteurs=nb_debiteurs,
            nb_creances=sum(creances_par_statut.values()),
            creances_par_statut=creances_par_statut,
            montant_total_initial=montant_total_initial,
            montant_total_restant=montant_total_restant,
            nb_paiements=nb_paiements,
            montant_total_encaisse=montant_total_encaisse,
            nb_relances=nb_relances,
            nb_utilisateurs=nb_utilisateurs,
            # Toutes les tranches sont renvoyees, y compris vides : le front affiche
            # un bandeau de largeur constante, sans trou selon les donnees du jour.
            balance_agee=[
                TrancheBalanceAgee(
                    tranche=nom,
                    montant=balance.get(nom, (Decimal("0"), 0))[0],
                    nb_creances=balance.get(nom, (Decimal("0"), 0))[1],
                )
                for nom in ("non-echu", "1-30", "31-60", "61-90", "90+")
            ],
            efficacite=Efficacite(
                periode_jours=periode,
                encours=encours,
                flux_periode=flux,
                dso=dso,
                delai_moyen=delai_moyen,
                cei=cei,
            ),
            balance_agee_historique=historique,
            echeances_a_venir=[MontantParMois(mois=m, montant=v) for m, v in echeances.items()],
            top_debiteurs=[
                LigneClassement(libelle=nom, montant=montant, nombre=nb) for nom, montant, nb in debiteurs
            ],
            encaissements_par_utilisateur=[
                LigneClassement(libelle=nom, montant=montant, nombre=nb) for nom, montant, nb in encaisseurs
            ],
            cartographie_risques=cartographie,
            promesses=promesses,
            previsions=previsions,
            productivite=productivite,
            alertes=alertes,
        )
