from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.exceptions import NotFoundException
from app.ia.assistant import ENTETE_PORTEFEUILLE, SYSTEM_PORTEFEUILLE
from app.ia.dependencies import AssistantIADep
from app.ia.recommandations import RecommandationsIA, get_recommandations_ia
from app.ia.schemas import AssistantRequest, AssistantResponse
from app.organisations.dependencies import OrganisationServiceDep, OrganisationStatsServiceDep
from app.organisations.schemas import ApercuOrganisation, OrganisationCreate, RecommandationsResponse, RecouvrementCompare, OrganisationRead, OrganisationStats, OrganisationUpdate
from app.users.dependencies import CurrentSuperAdminDep, CurrentUserDep

router = APIRouter(prefix="/organisations", tags=["organisations"])


@router.post("", response_model=OrganisationRead, status_code=status.HTTP_201_CREATED)
async def create_organisation(
    data: OrganisationCreate, service: OrganisationServiceDep, _super_admin: CurrentSuperAdminDep
) -> OrganisationRead:
    organisation = await service.create_organisation(data)
    return OrganisationRead.model_validate(organisation)


@router.get("", response_model=list[OrganisationRead])
async def list_organisations(
    service: OrganisationServiceDep,
    _super_admin: CurrentSuperAdminDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[OrganisationRead]:
    organisations = await service.list_organisations(skip=skip, limit=limit)
    return [OrganisationRead.model_validate(o) for o in organisations]


@router.get("/me", response_model=OrganisationRead)
async def get_my_organisation(current_user: CurrentUserDep, service: OrganisationServiceDep) -> OrganisationRead:
    if current_user.organisation_id is None:
        raise NotFoundException("Le SUPER_ADMIN n'appartient a aucune organisation")
    organisation = await service.get_organisation(current_user.organisation_id)
    return OrganisationRead.model_validate(organisation)


@router.get("/me/stats", response_model=OrganisationStats)
async def get_my_organisation_stats(
    current_user: CurrentUserDep,
    service: OrganisationStatsServiceDep,
    periode_jours: int = Query(
        90, ge=7, le=730, description="Fenetre glissante, en jours, des indicateurs d'efficacite"
    ),
) -> OrganisationStats:
    if current_user.organisation_id is None:
        raise NotFoundException("Le SUPER_ADMIN n'appartient a aucune organisation")
    return await service.get_stats(current_user.organisation_id, periode_jours)


@router.post("/me/recommandations", response_model=RecommandationsResponse)
async def recommandations_portefeuille(
    current_user: CurrentUserDep,
    service: OrganisationStatsServiceDep,
    ia: Annotated[RecommandationsIA, Depends(get_recommandations_ia)],
) -> RecommandationsResponse:
    """Actions prioritaires deduites de l'etat du portefeuille.

    Recalcule les statistiques a la demande plutot que de les recevoir du client :
    des chiffres transmis par le navigateur pourraient etre alteres, et le modele
    conseillerait alors sur un etat qui n'existe pas.
    """
    if current_user.organisation_id is None:
        raise NotFoundException("Le SUPER_ADMIN n'appartient a aucune organisation")

    stats = await service.get_stats(current_user.organisation_id)
    recommandations, modele = await ia.generer(stats)
    return RecommandationsResponse(recommandations=recommandations, modele=modele)


def _appuis_portefeuille(stats: OrganisationStats) -> list[str]:
    """Ce que le modele avait sous les yeux, en clair.

    Calcule ici et jamais par le modele : c'est ce qui rend son avis
    verifiable, et ce qui montre a l'agent ce qu'il ne pouvait PAS savoir.
    """
    lignes = [f"encours {stats.montant_total_restant} sur {stats.nb_creances} creance(s)"]

    tranches = [t for t in stats.balance_agee if t.montant > 0]
    if tranches:
        lignes.append("balance agee : " + ", ".join(f"{t.tranche} {t.montant}" for t in tranches))

    eff = stats.efficacite
    mesures = []
    if eff.dso is not None:
        mesures.append(f"DSO {eff.dso} j")
    if eff.delai_moyen is not None:
        mesures.append(f"delai constate {eff.delai_moyen} j")
    if eff.cei is not None:
        mesures.append(f"CEI {eff.cei} %")
    if mesures:
        lignes.append(" · ".join(mesures) + f" sur {eff.periode_jours} j")

    if stats.top_debiteurs:
        lignes.append(f"{len(stats.top_debiteurs)} principaux debiteurs")
    if stats.productivite:
        lignes.append(f"activite de {len(stats.productivite)} agent(s)")
    if stats.alertes:
        lignes.append(f"{len(stats.alertes)} alerte(s)")
    return lignes


@router.post("/me/assistant", response_model=AssistantResponse)
async def interroger_assistant_portefeuille(
    data: AssistantRequest,
    current_user: CurrentUserDep,
    service: OrganisationStatsServiceDep,
    assistant: AssistantIADep,
) -> AssistantResponse:
    """Repond a une question sur l'etat du portefeuille.

    Les statistiques sont recalculees ici plutot que recues du navigateur :
    des chiffres transmis par le client pourraient etre alteres, et le modele
    commenterait alors un portefeuille qui n'existe pas.

    Passe payante a chaque question, d'ou le POST : rien ne part a l'affichage
    du tableau de bord.
    """
    if current_user.organisation_id is None:
        raise NotFoundException("Le SUPER_ADMIN n'appartient a aucune organisation")

    stats = await service.get_stats(current_user.organisation_id)

    # Ce qui est transmis au modele : l'etat calcule, moins ce qui ne l'aiderait
    # pas a conseiller — l'historique mensuel est volumineux et souvent vide sur
    # un portefeuille jeune, la cartographie ne dit rien quand elle est vide.
    faits = stats.model_dump(
        mode="json",
        exclude={"organisation_id", "balance_agee_historique", "nb_utilisateurs"},
    )

    echanges = [{"role": tour.role, "content": tour.contenu} for tour in data.echanges]
    reponse, modele = await assistant.repondre(
        faits, echanges, system=SYSTEM_PORTEFEUILLE, entete=ENTETE_PORTEFEUILLE
    )
    return AssistantResponse(reponse=reponse, appuis=_appuis_portefeuille(stats), modele=modele)


@router.get("/apercu", response_model=list[ApercuOrganisation])
async def apercu_organisations(
    service: OrganisationStatsServiceDep, _super_admin: CurrentSuperAdminDep
) -> list[ApercuOrganisation]:
    return await service.apercu_organisations()


@router.get("/{organisation_id}", response_model=OrganisationRead)
async def get_organisation(
    organisation_id: int, service: OrganisationServiceDep, _super_admin: CurrentSuperAdminDep
) -> OrganisationRead:
    organisation = await service.get_organisation(organisation_id)
    return OrganisationRead.model_validate(organisation)


@router.get("/recouvrement-compare", response_model=RecouvrementCompare)
async def recouvrement_compare(
    service: OrganisationStatsServiceDep,
    _super_admin: CurrentSuperAdminDep,
    nb_mois: int = Query(6, ge=2, le=24, description="Nombre de mois calendaires, mois courant inclus"),
) -> RecouvrementCompare:
    return await service.recouvrement_compare(nb_mois)


@router.get("/plateforme/stats", response_model=OrganisationStats)
async def get_stats_plateforme(
    service: OrganisationStatsServiceDep,
    _super_admin: CurrentSuperAdminDep,
    periode_jours: int = Query(
        90, ge=7, le=730, description="Fenetre glissante, en jours, des indicateurs d'efficacite"
    ),
) -> OrganisationStats:
    """Agregat de toutes les organisations. Reserve au SUPER_ADMIN."""
    return await service.get_stats(None, periode_jours)


@router.get("/{organisation_id}/stats", response_model=OrganisationStats)
async def get_organisation_stats(
    organisation_id: int,
    service: OrganisationStatsServiceDep,
    _super_admin: CurrentSuperAdminDep,
    periode_jours: int = Query(
        90, ge=7, le=730, description="Fenetre glissante, en jours, des indicateurs d'efficacite"
    ),
) -> OrganisationStats:
    return await service.get_stats(organisation_id, periode_jours)


@router.patch("/{organisation_id}", response_model=OrganisationRead)
async def update_organisation(
    organisation_id: int,
    data: OrganisationUpdate,
    service: OrganisationServiceDep,
    _super_admin: CurrentSuperAdminDep,
) -> OrganisationRead:
    organisation = await service.update_organisation(organisation_id, data)
    return OrganisationRead.model_validate(organisation)


@router.delete("/{organisation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organisation(
    organisation_id: int, service: OrganisationServiceDep, _super_admin: CurrentSuperAdminDep
) -> None:
    await service.delete_organisation(organisation_id)
