from datetime import date, datetime
from decimal import Decimal
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.creances.models import StatutCreance


class CreanceBase(BaseModel):
    debiteur_id: int
    #: Le dossier dont cette facture fait partie. Obligatoire : toute creance
    #: appartient a une demande confiee par un client.
    dossier_id: int
    # Numero de la facture d'origine, celui que le debiteur reconnait.
    numero_facture: str | None = None
    description: str | None = None
    montant_initial: Decimal = Field(gt=0)
    # Facultative : les reprises de stock ne l'ont pas toujours. Quand elle est
    # connue, c'est elle — et non la date de saisie — qui date la creance.
    date_facture: date | None = None
    date_echeance: date

    # Contexte du dossier : axes de segmentation, alimentes par l'import Excel.
    etablissement: str | None = Field(default=None, max_length=255)
    cycle: str | None = Field(default=None, max_length=100)
    financeur: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _facture_avant_echeance(self) -> Self:
        if self.date_facture is not None and self.date_facture > self.date_echeance:
            raise ValueError("La date de facture ne peut pas etre posterieure a la date d'echeance")
        return self


class CreanceCreate(CreanceBase):
    # Optionnelle : si absente, le service génère une référence unique par organisation.
    reference: str | None = None
    statut: StatutCreance = StatutCreance.EN_COURS


class CreanceUpdate(BaseModel):
    reference: str | None = None
    numero_facture: str | None = None
    description: str | None = None
    date_facture: date | None = None
    date_echeance: date | None = None
    statut: StatutCreance | None = None
    etablissement: str | None = Field(default=None, max_length=255)
    cycle: str | None = Field(default=None, max_length=100)
    financeur: str | None = Field(default=None, max_length=255)


class CreanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    debiteur_id: int
    dossier_id: int
    reference: str
    numero_facture: str | None
    description: str | None
    montant_initial: Decimal
    montant_restant: Decimal
    date_facture: date | None
    date_saisie: date
    date_echeance: date
    statut: StatutCreance
    etablissement: str | None
    cycle: str | None
    financeur: str | None
    created_at: datetime
    updated_at: datetime
