from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.paiements.models import ModePaiement


class PaiementBase(BaseModel):
    creance_id: int
    montant: Decimal = Field(gt=0)
    date_paiement: date = Field(default_factory=date.today)
    mode_paiement: ModePaiement
    reference: str | None = None
    notes: str | None = None


class PaiementCreate(PaiementBase):
    pass


class PaiementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    creance_id: int
    montant: Decimal
    date_paiement: date
    mode_paiement: ModePaiement
    reference: str | None
    notes: str | None
    saisi_par_nom: str | None
    created_at: datetime
