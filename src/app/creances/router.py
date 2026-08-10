from fastapi import APIRouter, Query, status

from app.creances.dependencies import CreanceServiceDep
from app.creances.models import StatutCreance
from app.creances.schemas import CreanceCreate, CreanceRead, CreanceUpdate
from app.debiteurs.dependencies import DebiteurServiceDep
from app.ia.dependencies import RedactionServiceDep
from app.ia.schemas import MessageRelanceRequest, MessageRelanceResponse
from app.organisations.dependencies import OrganisationServiceDep
from app.relances.dependencies import RelanceServiceDep
from app.users.dependencies import CurrentAdminDep, CurrentUserDep

router = APIRouter(prefix="/creances", tags=["creances"])


@router.post("", response_model=CreanceRead, status_code=status.HTTP_201_CREATED)
async def create_creance(data: CreanceCreate, service: CreanceServiceDep) -> CreanceRead:
    creance = await service.create_creance(data)
    return CreanceRead.model_validate(creance)


@router.get("", response_model=list[CreanceRead])
async def list_creances(
    service: CreanceServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    debiteur_id: int | None = None,
    statut: StatutCreance | None = None,
) -> list[CreanceRead]:
    creances = await service.list_creances(skip=skip, limit=limit, debiteur_id=debiteur_id, statut=statut)
    return [CreanceRead.model_validate(c) for c in creances]


# Declaree AVANT /{creance_id} : sinon FastAPI tente d'abord de lire
# « by-reference » comme un entier et renvoie 422 au lieu d'atteindre cette route.
# La reference passe en query et non en segment d'URL : elle est libre a la
# creation et peut contenir une barre oblique (« SOF/TRD/08/2025 »), qui couperait
# le chemin en deux.
@router.get("/by-reference", response_model=CreanceRead)
async def get_creance_par_reference(
    service: CreanceServiceDep, reference: str = Query(min_length=1, max_length=50)
) -> CreanceRead:
    """Resout une creance depuis sa reference, pour les URLs lisibles du front."""
    creance = await service.get_creance_par_reference(reference)
    return CreanceRead.model_validate(creance)


@router.get("/{creance_id}", response_model=CreanceRead)
async def get_creance(creance_id: int, service: CreanceServiceDep) -> CreanceRead:
    creance = await service.get_creance(creance_id)
    return CreanceRead.model_validate(creance)


@router.patch("/{creance_id}", response_model=CreanceRead)
async def update_creance(creance_id: int, data: CreanceUpdate, service: CreanceServiceDep) -> CreanceRead:
    creance = await service.update_creance(creance_id, data)
    return CreanceRead.model_validate(creance)


@router.delete("/{creance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creance(creance_id: int, service: CreanceServiceDep, _: CurrentAdminDep) -> None:
    await service.delete_creance(creance_id)


@router.post("/{creance_id}/message-relance", response_model=MessageRelanceResponse)
async def rediger_message_relance(
    creance_id: int,
    data: MessageRelanceRequest,
    service: CreanceServiceDep,
    debiteur_service: DebiteurServiceDep,
    relance_service: RelanceServiceDep,
    organisation_service: OrganisationServiceDep,
    redaction: RedactionServiceDep,
    current_user: CurrentUserDep,
) -> MessageRelanceResponse:
    """Redige un message de relance a partir du dossier.

    L'autorisation est portee par la creance : get_creance verifie deja que
    l'utilisateur a acces a ce dossier, donc l'endpoint n'a pas de garde propre.
    current_user sert a signer le message, pas a autoriser l'appel.
    """
    creance = await service.get_creance(creance_id)
    debiteur = await debiteur_service.get_debiteur(creance.debiteur_id)
    # L'historique est celui du dossier : les relances precedentes couvraient
    # toutes les factures du debiteur, pas seulement celle-ci.
    relances = await relance_service.list_relances(dossier_id=creance.dossier_id, limit=50)
    # Charge explicitement : la relation User.organisation est lazy, y acceder
    # depuis current_user leverait MissingGreenlet en session async.
    organisation = (
        await organisation_service.get_organisation(current_user.organisation_id)
        if current_user.organisation_id is not None
        else None
    )

    message, modele = await redaction.generer_message(
        creance, debiteur, relances, data, current_user, organisation
    )
    return MessageRelanceResponse(message=message, modele=modele)
