from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.ia.segmentation import ClassificationIA, get_classification_ia
from app.segmentation.repository import SegmentationRepository
from app.segmentation.service import SegmentationService
from app.users.dependencies import CurrentUserDep


def get_segmentation_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    classification: Annotated[ClassificationIA, Depends(get_classification_ia)],
    current_user: CurrentUserDep,
) -> SegmentationService:
    return SegmentationService(SegmentationRepository(db), classification, current_user)


SegmentationServiceDep = Annotated[SegmentationService, Depends(get_segmentation_service)]
