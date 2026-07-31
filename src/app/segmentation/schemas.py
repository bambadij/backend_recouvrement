from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.segmentation.models import PotentielRecouvrement, SegmentRisque


class FaitsDossier(BaseModel):
    """Les faits chiffres d'un dossier, calcules en Python.

    Rien ici ne sort d'un modele de langage : ce sont des comptages et des
    soustractions de dates. Le modele classe a partir de ce bloc, il ne le produit
    pas — c'est ce qui rend un classement rejouable et verifiable.
    """

    creance_id: int
    reference: str
    debiteur: str
    entreprise: str | None = None
    etablissement: str | None = None
    cycle: str | None = None
    financeur: str | None = None

    montant_initial: Decimal
    montant_restant: Decimal
    taux_regle: int
    #: Jours ecoules depuis l'echeance. Negatif tant qu'elle est a venir.
    anciennete_jours: int
    statut: str

    nb_relances: int
    nb_relances_echouees: int
    jours_depuis_derniere_relance: int | None = None

    nb_paiements: int
    jours_depuis_dernier_paiement: int | None = None

    nb_promesses: int
    nb_promesses_tenues: int
    nb_promesses_rompues: int


class SegmentationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creance_id: int
    segment: SegmentRisque
    potentiel: PotentielRecouvrement
    justification: str
    anciennete_jours: int
    taux_regle: int
    nb_relances: int
    nb_promesses_rompues: int
    modele: str
    calcule_le: datetime


class DossierSegmente(BaseModel):
    """Une ligne de la file de travail : la creance, son classement, son rang."""

    creance_id: int
    reference: str
    debiteur: str
    etablissement: str | None
    cycle: str | None
    financeur: str | None
    montant_restant: Decimal
    date_echeance: date
    anciennete_jours: int

    segment: SegmentRisque
    potentiel: PotentielRecouvrement
    justification: str
    #: Rang de traitement, 1 = a travailler en premier. Calcule, non stocke.
    rang: int
    calcule_le: datetime


class SegmentationRequest(BaseModel):
    #: Plafond de dossiers traites dans la passe. Chaque lot part en un appel.
    limite: int = Field(default=200, ge=1, le=1000)
    #: Par defaut on ignore les dossiers deja classes recemment. Force le recalcul.
    forcer: bool = False


class SegmentationRunResult(BaseModel):
    dossiers_analyses: int
    dossiers_classes: int
    #: Dossiers ignores car deja classes et inchanges depuis.
    ignores: int
    repartition: dict[str, int]
    modele: str
