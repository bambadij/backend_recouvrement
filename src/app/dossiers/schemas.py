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


class EncoursDebiteur(BaseModel):
    nom: str
    nb_creances: int
    montant_restant: Decimal
    #: Jours de retard de sa facture la plus ancienne.
    retard_max_jours: int
    #: Engagements non tenus. Un debiteur qui promet et ne paie pas ne se
    #: retravaille pas comme un debiteur simplement silencieux.
    promesses_rompues: int = 0
    #: Derniere relance effectivement partie. Nul si on ne l'a jamais relance.
    derniere_relance: date | None = None


class FaitsDossier(BaseModel):
    """L'etat chiffre d'un dossier, calcule en Python.

    Rien ici ne sort d'un modele de langage : ce sont des comptages, des sommes
    et des soustractions de dates. Le modele lit ce bloc pour arbitrer, il ne le
    produit pas — c'est ce qui l'empeche de contredire les chiffres affiches.
    """

    reference: str | None
    client: str
    creancier: str
    type_dossier: TypeDossier
    objectif: ObjectifDossier
    statut: StatutDossier
    date_reception: date
    #: Jours ecoules depuis la remise du dossier par le client.
    anciennete_jours: int

    nb_creances: int
    nb_debiteurs: int
    montant_confie: Decimal
    montant_restant: Decimal
    montant_encaisse: Decimal
    #: Part deja recouvree, en pourcent du montant confie.
    taux_recouvrement: int

    creances_par_statut: dict[str, int]
    #: Encours par tranche d'anciennete : « a jour », « 1-30 j », « 31-60 j »…
    balance_agee: dict[str, Decimal]
    #: Encours par debiteur, du plus lourd au plus leger.
    debiteurs: list[EncoursDebiteur]

    relances_par_canal: dict[str, int]
    relances_echouees: int
    #: Jour de la derniere relance partie, tous debiteurs confondus. Nul si aucune.
    derniere_relance: date | None
    promesses: dict[str, int]


class ActionDossier(BaseModel):
    """Une action a mener, telle que le modele la formule."""

    titre: str
    action: str
    #: Le chiffre qui la motive, repris des faits. Rend la recommandation verifiable.
    fait_declencheur: str
    urgence: str


class LecturesGraphiques(BaseModel):
    """Une phrase de lecture par graphique affiche.

    Ces legendes sont redigees et non figees : « la moitie de l'encours depasse
    90 jours » est vrai d'un dossier et faux du suivant. Une legende ecrite en
    dur finirait par mentir sous le graphe qu'elle pretend decrire.

    Vide quand le graphe n'a rien a montrer — l'interface masque alors la ligne
    plutot que d'afficher un commentaire de remplissage.
    """

    anciennete: str = ""
    debiteurs: str = ""
    engagements: str = ""


class AnalyseDossier(BaseModel):
    """Lecture du dossier par le modele, accompagnee des faits qui la fondent."""

    synthese: str
    actions: list[ActionDossier]
    lectures: LecturesGraphiques
    faits: FaitsDossier
    modele: str
