from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.promesses.models import SourcePromesse, StatutPromesse


class PromesseBase(BaseModel):
    dossier_id: int
    debiteur_id: int
    relance_id: int | None = None
    date_promesse: date = Field(default_factory=date.today)
    date_echeance_promesse: date
    montant_promis: Decimal = Field(gt=0)
    commentaire: str | None = Field(default=None, max_length=1000)


class PromesseCreate(PromesseBase):
    pass


class PromesseUpdate(BaseModel):
    date_echeance_promesse: date | None = None
    montant_promis: Decimal | None = Field(default=None, gt=0)
    statut: StatutPromesse | None = None
    commentaire: str | None = Field(default=None, max_length=1000)


class PromesseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    dossier_id: int
    relance_id: int | None
    date_promesse: date
    date_echeance_promesse: date
    montant_promis: Decimal
    statut: StatutPromesse
    source: SourcePromesse
    commentaire: str | None
    created_at: datetime


class ExtractionPromessesResult(BaseModel):
    """Bilan d'une passe d'inference sur les resultats de relance."""

    relances_analysees: int
    promesses_creees: int
    #: Relances dont le resultat ne contenait aucun engagement datable.
    sans_engagement: int
    modele: str


class ControlePromessesResult(BaseModel):
    """Bilan d'une passe de controle des promesses arrivees a echeance."""

    promesses_controlees: int
    tenues: int
    partielles: int
    rompues: int
