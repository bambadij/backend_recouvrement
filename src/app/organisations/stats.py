from datetime import date, timedelta
from decimal import Decimal

from app.clients.repository import ClientRepository
from app.core.exceptions import NotFoundException
from app.creances.repository import CreanceRepository
from app.organisations.repository import OrganisationRepository
from app.organisations.schemas import (
    ApercuOrganisation,
    RecouvrementCompare,
    SerieRecouvrement,
    Efficacite,
    LigneClassement,
    MontantParMois,
    OrganisationStats,
    PointBalanceAgee,
    TrancheBalanceAgee,
)
from app.paiements.repository import PaiementRepository
from app.relances.repository import RelanceRepository
from app.users.repository import UserRepository


class OrganisationStatsService:
    def __init__(
        self,
        organisation_repository: OrganisationRepository,
        client_repository: ClientRepository,
        creance_repository: CreanceRepository,
        paiement_repository: PaiementRepository,
        relance_repository: RelanceRepository,
        user_repository: UserRepository,
    ) -> None:
        self.organisation_repository = organisation_repository
        self.client_repository = client_repository
        self.creance_repository = creance_repository
        self.paiement_repository = paiement_repository
        self.relance_repository = relance_repository
        self.user_repository = user_repository

    #: Période glissante par défaut des indicateurs d'efficacité. Un trimestre :
    #: assez long pour absorber la saisonnalité des encaissements, assez court
    #: pour rester actuel. L'appelant peut la surcharger.
    PERIODE_EFFICACITE_JOURS = 90

    #: Profondeur de l'historique de balance âgée, en fins de mois.
    HISTORIQUE_MOIS = 6

    #: Horizon du calendrier des échéances à venir.
    HORIZON_MOIS = 6

    TOP_DEBITEURS = 5

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

        nb_clients = await self.client_repository.count(organisation_id)
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

        return OrganisationStats(
            organisation_id=organisation_id,
            nb_clients=nb_clients,
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
            ),
            balance_agee_historique=historique,
            echeances_a_venir=[MontantParMois(mois=m, montant=v) for m, v in echeances.items()],
            top_debiteurs=[
                LigneClassement(libelle=nom, montant=montant, nombre=nb) for nom, montant, nb in debiteurs
            ],
            encaissements_par_utilisateur=[
                LigneClassement(libelle=nom, montant=montant, nombre=nb) for nom, montant, nb in encaisseurs
            ],
        )
