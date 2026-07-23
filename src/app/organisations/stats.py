from app.clients.repository import ClientRepository
from app.core.exceptions import NotFoundException
from app.creances.repository import CreanceRepository
from app.organisations.repository import OrganisationRepository
from app.organisations.schemas import OrganisationStats
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

    async def get_stats(self, organisation_id: int) -> OrganisationStats:
        if await self.organisation_repository.get_by_id(organisation_id) is None:
            raise NotFoundException(f"Organisation {organisation_id} introuvable")

        nb_clients = await self.client_repository.count(organisation_id)
        creances_par_statut = await self.creance_repository.count_by_statut(organisation_id)
        montant_total_initial, montant_total_restant = await self.creance_repository.sum_montants(organisation_id)
        nb_paiements, montant_total_encaisse = await self.paiement_repository.stats(organisation_id)
        nb_relances = await self.relance_repository.count(organisation_id)
        nb_utilisateurs = await self.user_repository.count(organisation_id)

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
        )
