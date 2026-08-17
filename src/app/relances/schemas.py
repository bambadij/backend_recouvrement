from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.relances.models import StatutRelance, TypeRelance


class RelanceBase(BaseModel):
    dossier_id: int
    #: Le debiteur vise dans ce dossier : un dossier peut en compter trente.
    debiteur_id: int
    type_relance: TypeRelance
    date_relance: date = Field(default_factory=date.today)
    contenu: str | None = None


class RelanceCreate(RelanceBase):
    pass


class RelanceUpdate(BaseModel):
    statut: StatutRelance | None = None
    resultat: str | None = None


class FileDisponible(BaseModel):
    """Un critere de travail, avec le nombre de debiteurs qu'il retient."""

    cle: str
    libelle: str
    effectif: int


class LigneARelancer(BaseModel):
    """Un debiteur a relancer dans un dossier, toutes ses factures echues confondues.

    L'unite n'est pas la facture : une relance vise un debiteur A L'INTERIEUR
    d'un dossier, et un seul courrier couvre tous ses impayes. Presenter la file
    facture par facture ferait envoyer trois messages a quelqu'un qui doit trois
    factures.
    """

    dossier_id: int
    dossier_reference: str | None
    debiteur_id: int
    debiteur_nom: str
    #: Expose a part : les reprises de stock recopient souvent la raison sociale
    #: dans le nom, et l'interface doit pouvoir eviter de l'afficher deux fois.
    debiteur_entreprise: str | None

    nb_factures: int
    montant_restant: Decimal
    #: Retard de la facture la plus ancienne : c'est l'anciennete de la dette.
    jours_retard: int
    #: La plus ancienne facture echue, point d'entree vers la page de detail.
    creance_id: int

    #: Derniere relance PARTIE. Une relance planifiee n'a rien emis : la compter
    #: reviendrait a dire qu'on a relance quelqu'un qui n'a rien recu.
    derniere_relance: date | None
    derniere_relance_canal: TypeRelance | None
    #: Vrai si cette derniere relance a obtenu un retour (champ resultat rempli).
    derniere_relance_repondue: bool

    #: Relance deja planifiee et non emise, s'il y en a une. Sans ce temoin, la
    #: file afficherait « jamais relance » a cote d'une relance en attente et
    #: l'agent en creerait une seconde.
    relance_planifiee_id: int | None


class FileDeTravail(BaseModel):
    """La file du jour : les criteres disponibles, et les lignes de l'un d'eux."""

    file_active: str
    files: list[FileDisponible]
    lignes: list[LigneARelancer]


class RelanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    dossier_id: int
    debiteur_id: int
    type_relance: TypeRelance
    date_relance: date
    statut: StatutRelance
    contenu: str | None
    resultat: str | None
    cree_par_nom: str | None
    created_at: datetime
