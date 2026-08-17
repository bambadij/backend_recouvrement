from datetime import date

from fastapi import APIRouter, Query, status

from app.creances.dependencies import CreanceServiceDep
from app.creances.models import StatutCreance
from app.creances.schemas import CreanceCreate, CreanceRead, CreanceUpdate
from app.debiteurs.dependencies import DebiteurServiceDep
from app.debiteurs.schemas import FaitsDebiteur
from app.ia.dependencies import AssistantIADep, RedactionServiceDep
from app.ia.schemas import (
    AssistantRequest,
    AssistantResponse,
    MessageRelanceRequest,
    MessageRelanceResponse,
)
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
    #: Les factures d'une demande precise : c'est l'entree depuis la liste des dossiers.
    dossier_id: int | None = None,
    statut: StatutCreance | None = None,
) -> list[CreanceRead]:
    creances = await service.list_creances(
        skip=skip, limit=limit, debiteur_id=debiteur_id, dossier_id=dossier_id, statut=statut
    )
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


#: Libelles des canaux dans les appuis affiches sous la reponse.
_CANAUX = {
    "EMAIL": "relances email",
    "SMS": "SMS",
    "WHATSAPP": "messages WhatsApp",
    "APPEL": "appels",
    "COURRIER": "courriers",
    "MISE_EN_DEMEURE": "mises en demeure",
}


def _appuis(faits: FaitsDebiteur) -> list[str]:
    """Ce sur quoi la reponse s'appuie, en clair.

    Calcule ici et non par le modele : c'est precisement ce qui permet a l'agent
    de verifier l'avis qu'il vient de lire. Un modele qui redigerait lui-meme la
    liste de ses sources pourrait en inventer.
    """
    lignes = [f"{c.envoyees} {_CANAUX.get(c.canal, c.canal.lower())}" for c in faits.canaux]
    if faits.nb_soldees:
        lignes.append(f"{faits.nb_soldees} facture(s) soldee(s)")
    rompues = faits.promesses.get("ROMPUE", 0)
    if rompues:
        lignes.append(f"{rompues} promesse(s) rompue(s)")
    return lignes


@router.post("/{creance_id}/assistant", response_model=AssistantResponse)
async def interroger_assistant(
    creance_id: int,
    data: AssistantRequest,
    service: CreanceServiceDep,
    debiteur_service: DebiteurServiceDep,
    assistant: AssistantIADep,
) -> AssistantResponse:
    """Repond a une question de l'agent sur cette creance.

    L'autorisation est portee par la creance : get_creance verifie deja l'acces,
    et faits_debiteur verifie l'organisation du debiteur.

    Passe payante a chaque question, d'ou le POST : rien ne part a l'affichage.
    """
    creance = await service.get_creance(creance_id)
    faits_debiteur = await debiteur_service.faits_debiteur(creance.debiteur_id)

    # La facture regardee, plus l'histoire de celui qui la doit. Le modele a
    # besoin des deux : le retard se lit sur la facture, le comportement sur le
    # debiteur.
    faits = {
        "facture": {
            "reference": creance.reference,
            "montant_initial": str(creance.montant_initial),
            "montant_restant": str(creance.montant_restant),
            "date_echeance": creance.date_echeance.isoformat(),
            "jours_retard": (date.today() - creance.date_echeance).days,
            "statut": creance.statut.value,
        },
        "debiteur": faits_debiteur.model_dump(mode="json"),
    }

    echanges = [
        {"role": tour.role, "content": tour.contenu} for tour in data.echanges
    ]
    reponse, modele = await assistant.repondre(faits, echanges)
    return AssistantResponse(reponse=reponse, appuis=_appuis(faits_debiteur), modele=modele)
