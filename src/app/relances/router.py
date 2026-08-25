from fastapi import APIRouter, Query, status

from app.relances.dependencies import RelanceServiceDep
from app.relances.models import StatutRelance
from app.relances.schemas import (
    FileDeTravail,
    IssueRelanceRequest,
    RelanceCreate,
    RelanceRead,
    RelanceUpdate,
)
from app.users.dependencies import CurrentAdminDep

router = APIRouter(prefix="/relances", tags=["relances"])


@router.post("", response_model=RelanceRead, status_code=status.HTTP_201_CREATED)
async def create_relance(data: RelanceCreate, service: RelanceServiceDep) -> RelanceRead:
    relance = await service.create_relance(data)
    return RelanceRead.model_validate(relance)


@router.get("", response_model=list[RelanceRead])
async def list_relances(
    service: RelanceServiceDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    dossier_id: int | None = None,
    debiteur_id: int | None = None,
    statut: StatutRelance | None = None,
    avec_resultat: bool | None = Query(
        None, description="true : uniquement les relances portant un resultat (engagement obtenu)"
    ),
) -> list[RelanceRead]:
    relances = await service.list_relances(
        skip=skip, limit=limit, dossier_id=dossier_id, debiteur_id=debiteur_id, statut=statut, avec_resultat=avec_resultat
    )
    return [RelanceRead.model_validate(r) for r in relances]


# Declare avant « /{relance_id} » : sinon « a-faire » serait pris pour un
# identifiant et la route repondrait 422.
@router.get("/a-faire", response_model=FileDeTravail)
async def file_de_travail(
    service: RelanceServiceDep,
    file: str | None = Query(
        None, description="retard | jamais_relance | sans_reponse | gros_montant"
    ),
    limit: int = Query(100, ge=1, le=500),
    tri: str | None = Query(None, description="classement | montant"),
) -> FileDeTravail:
    """Par quoi commencer aujourd'hui : les debiteurs a relancer, par critere.

    Lecture pure, y compris pour le classement : celui-ci est lu en base tel
    qu'une passe l'a laisse. Aucun appel de modele n'est declenche ici, quel que
    soit le role de l'appelant.
    """
    return await service.file_de_travail(file=file, limit=limit, tri=tri)


@router.get("/{relance_id}", response_model=RelanceRead)
async def get_relance(relance_id: int, service: RelanceServiceDep) -> RelanceRead:
    relance = await service.get_relance(relance_id)
    return RelanceRead.model_validate(relance)


@router.post("/{relance_id}/issue", response_model=RelanceRead)
async def enregistrer_issue(
    relance_id: int, data: IssueRelanceRequest, service: RelanceServiceDep
) -> RelanceRead:
    """Consigne ce que la relance a produit, et l'engagement s'il y en a un.

    Un seul geste : l'agent raccroche, choisit l'issue, et si le debiteur s'est
    engage il donne le montant et l'echeance. La promesse est creee dans la
    foulee, SAISIE — pas besoin d'un appel de modele pour relire une phrase que
    l'agent aurait ecrite a la place.

    Aucune contrainte de statut : une relance s'annote surtout apres son envoi,
    et une issue se corrige.
    """
    relance = await service.enregistrer_issue(relance_id, data)
    return RelanceRead.model_validate(relance)


@router.patch("/{relance_id}", response_model=RelanceRead)
async def update_relance(relance_id: int, data: RelanceUpdate, service: RelanceServiceDep) -> RelanceRead:
    relance = await service.update_relance(relance_id, data)
    return RelanceRead.model_validate(relance)


@router.delete("/{relance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_relance(relance_id: int, service: RelanceServiceDep, _: CurrentAdminDep) -> None:
    await service.delete_relance(relance_id)
