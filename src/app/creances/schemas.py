from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.creances.models import StatutCreance


class CreanceBase(BaseModel):
    client_id: int
    description: str | None = None
    montant_initial: Decimal = Field(gt=0)
    date_echeance: date

    # Contexte du dossier : axes de segmentation, alimentes par l'import Excel.
    etablissement: str | None = Field(default=None, max_length=255)
    cycle: str | None = Field(default=None, max_length=100)
    financeur: str | None = Field(default=None, max_length=255)


class CreanceCreate(CreanceBase):
    # Optionnelle : si absente, le service génère une référence unique par organisation.
    reference: str | None = None
    statut: StatutCreance = StatutCreance.EN_COURS


class CreanceUpdate(BaseModel):
    reference: str | None = None
    description: str | None = None
    date_echeance: date | None = None
    statut: StatutCreance | None = None
    etablissement: str | None = Field(default=None, max_length=255)
    cycle: str | None = Field(default=None, max_length=100)
    financeur: str | None = Field(default=None, max_length=255)


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
    etablissement: str | None
    cycle: str | None
    financeur: str | None
    created_at: datetime
    updated_at: datetime
