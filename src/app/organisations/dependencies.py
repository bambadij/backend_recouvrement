from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.repository import ClientRepository
from app.core.database import get_db
from app.creances.repository import CreanceRepository
from app.organisations.repository import OrganisationRepository
from app.organisations.service import OrganisationService
from app.organisations.stats import OrganisationStatsService
from app.paiements.repository import PaiementRepository
from app.promesses.repository import PromesseRepository
from app.relances.repository import RelanceRepository
from app.segmentation.repository import SegmentationRepository
from app.users.repository import UserRepository


def get_organisation_service(db: Annotated[AsyncSession, Depends(get_db)]) -> OrganisationService:
    return OrganisationService(OrganisationRepository(db))


OrganisationServiceDep = Annotated[OrganisationService, Depends(get_organisation_service)]


def get_organisation_stats_service(db: Annotated[AsyncSession, Depends(get_db)]) -> OrganisationStatsService:
    return OrganisationStatsService(
        OrganisationRepository(db),
        ClientRepository(db),
        CreanceRepository(db),
        PaiementRepository(db),
        RelanceRepository(db),
        UserRepository(db),
        SegmentationRepository(db),
        PromesseRepository(db),
    )


OrganisationStatsServiceDep = Annotated[OrganisationStatsService, Depends(get_organisation_stats_service)]
