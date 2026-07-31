from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.relances.models import StatutRelance, TypeRelance


class RelanceBase(BaseModel):
    creance_id: int
    type_relance: TypeRelance
    date_relance: date = Field(default_factory=date.today)
    contenu: str | None = None


class RelanceCreate(RelanceBase):
    pass


class RelanceUpdate(BaseModel):
    statut: StatutRelance | None = None
    resultat: str | None = None


class RelanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    creance_id: int
    type_relance: TypeRelance
    date_relance: date
    statut: StatutRelance
    contenu: str | None
    resultat: str | None
    cree_par_nom: str | None
    created_at: datetime
