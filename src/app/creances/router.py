from fastapi import APIRouter, Query, status

from app.creances.dependencies import CreanceServiceDep
from app.creances.models import StatutCreance
from app.clients.dependencies import ClientServiceDep
from app.creances.schemas import CreanceCreate, CreanceRead, CreanceUpdate
from app.ia.dependencies import RedactionServiceDep
from app.ia.schemas import MessageRelanceRequest, MessageRelanceResponse
from app.relances.dependencies import RelanceServiceDep

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
    client_id: int | None = None,
    statut: StatutCreance | None = None,
) -> list[CreanceRead]:
    creances = await service.list_creances(skip=skip, limit=limit, client_id=client_id, statut=statut)
    return [CreanceRead.model_validate(c) for c in creances]


@router.get("/{creance_id}", response_model=CreanceRead)
async def get_creance(creance_id: int, service: CreanceServiceDep) -> CreanceRead:
    creance = await service.get_creance(creance_id)
    return CreanceRead.model_validate(creance)


@router.patch("/{creance_id}", response_model=CreanceRead)
async def update_creance(creance_id: int, data: CreanceUpdate, service: CreanceServiceDep) -> CreanceRead:
    creance = await service.update_creance(creance_id, data)
    return CreanceRead.model_validate(creance)


@router.delete("/{creance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_creance(creance_id: int, service: CreanceServiceDep) -> None:
    await service.delete_creance(creance_id)


@router.post("/{creance_id}/message-relance", response_model=MessageRelanceResponse)
async def rediger_message_relance(
    creance_id: int,
    data: MessageRelanceRequest,
    service: CreanceServiceDep,
    client_service: ClientServiceDep,
    relance_service: RelanceServiceDep,
    redaction: RedactionServiceDep,
) -> MessageRelanceResponse:
    """Redige un message de relance a partir du dossier.

    L'autorisation est portee par la creance : get_creance verifie deja que
    l'utilisateur a acces a ce dossier, donc l'endpoint n'a pas de garde propre.
    """
    creance = await service.get_creance(creance_id)
    client = await client_service.get_client(creance.client_id)
    relances = await relance_service.list_relances(creance_id=creance_id, limit=50)

    message, modele = await redaction.generer_message(creance, client, relances, data)
    return MessageRelanceResponse(message=message, modele=modele)
