from app.clients.service import ClientService
from app.core.exceptions import BadRequestException, ConflictException, ForbiddenException, NotFoundException
from app.creanciers.service import CreancierService
from app.dossiers.models import Dossier, StatutDossier
from app.dossiers.repository import DossierRepository
from app.dossiers.schemas import DossierCreate, DossierListItem, DossierUpdate
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
