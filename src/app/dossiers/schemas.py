from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.dossiers.models import ObjectifDossier, StatutDossier, TypeDossier


class DossierBase(BaseModel):
    client_id: int
    #: Vide = le creancier est le client lui-meme.
    creancier_id: int | None = None
    #: Reference du client. Champ libre : les formats varient d'un client a l'autre.
    reference: str | None = None
    date_reception: date | None = None
    type_dossier: TypeDossier = TypeDossier.LOCAL
    objectif: ObjectifDossier = ObjectifDossier.AMIABLE
    notes: str | None = None


class DossierCreate(DossierBase):
    pass


class DossierUpdate(BaseModel):
    client_id: int | None = None
    creancier_id: int | None = None
    reference: str | None = None
    date_reception: date | None = None
    type_dossier: TypeDossier | None = None
    objectif: ObjectifDossier | None = None
    statut: StatutDossier | None = None
    notes: str | None = None


class DossierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    client_id: int
    creancier_id: int | None
    reference: str | None
    date_reception: date
    type_dossier: TypeDossier
    objectif: ObjectifDossier
    statut: StatutDossier
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DossierListItem(DossierRead):
    """Dossier enrichi pour l'affichage en liste.

    Les noms et les totaux sont agreges en SQL : sans cela, afficher cent
    dossiers demanderait des centaines d'appels supplementaires.
    """

    client_nom: str
    #: Nom du creancier, ou celui du client quand les deux se confondent.
    creancier_nom: str
    #: Vrai quand le creancier est le client lui-meme.
    creancier_est_client: bool
    nb_creances: int
    nb_debiteurs: int
    montant_initial: Decimal
    montant_restant: Decimal
