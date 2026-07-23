from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrganisationBase(BaseModel):
    nom: str
    description: str | None = None


class OrganisationCreate(OrganisationBase):
    pass


class OrganisationUpdate(BaseModel):
    nom: str | None = None
    description: str | None = None
    is_active: bool | None = None


class OrganisationRead(OrganisationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class OrganisationStats(BaseModel):
    organisation_id: int
    nb_clients: int
    nb_creances: int
    creances_par_statut: dict[str, int]
    montant_total_initial: Decimal
    montant_total_restant: Decimal
    nb_paiements: int
    montant_total_encaisse: Decimal
    nb_relances: int
    nb_utilisateurs: int
