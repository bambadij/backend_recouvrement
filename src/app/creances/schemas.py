from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.creances.models import StatutCreance


class CreanceBase(BaseModel):
    client_id: int
    reference: str
    description: str | None = None
    montant_initial: Decimal = Field(gt=0)
    date_echeance: date


class CreanceCreate(CreanceBase):
    pass


class CreanceUpdate(BaseModel):
    reference: str | None = None
    description: str | None = None
    date_echeance: date | None = None
    statut: StatutCreance | None = None


class CreanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    client_id: int
    reference: str
    description: str | None
    montant_initial: Decimal
    montant_restant: Decimal
    date_creation: date
    date_echeance: date
    statut: StatutCreance
    created_at: datetime
    updated_at: datetime
