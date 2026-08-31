from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr


class DebiteurBase(BaseModel):
    nom: str
    prenom: str
    email: EmailStr | None = None
    telephone: str | None = None
    adresse: str | None = None
    ville: str | None = None
    code_postal: str | None = None
    entreprise: str | None = None
    notes: str | None = None


class DebiteurCreate(DebiteurBase):
    pass


class DebiteurUpdate(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None
    adresse: str | None = None
    ville: str | None = None
    code_postal: str | None = None
    entreprise: str | None = None
    notes: str | None = None


class DebiteurRead(DebiteurBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime


class CanalDebiteur(BaseModel):
    """Ce qui a ete tente sur ce debiteur, canal par canal, et ce qui a repondu."""

    canal: str
    envoyees: int
    #: Relances dont le champ « resultat » est renseigne : le debiteur a reagi.
    avec_reponse: int


class DelaiReglement(BaseModel):
    """Combien de jours ce debiteur a mis a payer une facture desormais soldee."""

    reference: str
    date_echeance: date
    #: Jour du dernier encaissement ayant solde la facture.
    date_solde: date
    #: Negatif quand la facture a ete reglee avant son echeance.
    jours: int


class FactureDebiteur(BaseModel):
    """Une facture de ce debiteur, avec ce qui en a deja ete regle.

    Le seul graphique qui a des donnees des la premiere facture : les delais de
    reglement demandent une facture soldee, les promesses un engagement obtenu,
    le taux de reponse un champ que personne ne remplit toujours.
    """

    reference: str
    montant_initial: Decimal
    montant_restant: Decimal
    statut: str
    date_echeance: date
    #: Negatif tant que l'echeance est a venir.
    jours_retard: int


class FaitsDebiteur(BaseModel):
    """L'etat chiffre d'un debiteur, toutes ses factures confondues.

    Sert a situer une creance dans l'histoire du debiteur : la page de detail
    ne montre qu'une facture, alors que la decision — quel canal, quel ton,
    quel echeancier — se prend au vu de son comportement d'ensemble.

    Comme partout ailleurs : Python calcule, le modele redige.
    """

    nom: str
    entreprise: str | None
    #: Date de la premiere facture confiee. Le « client depuis ».
    premiere_creance: date | None

    nb_creances: int
    nb_soldees: int
    encours_total: Decimal
    #: Ses factures, de la plus ancienne echeance a la plus recente.
    factures: list[FactureDebiteur]

    canaux: list[CanalDebiteur]
    #: Vrai des qu'au moins une relance porte un resultat.
    #:
    #: Sans ce temoin, un taux de reponse a zero partout se lirait comme « ce
    #: debiteur ne repond jamais », alors qu'il signifie « personne n'a rempli
    #: le champ ». L'interface masque le taux et retombe sur le simple compte.
    reponses_tracees: bool

    #: Ses factures soldees, de la plus ancienne a la plus recente.
    delais: list[DelaiReglement]
    promesses: dict[str, int]
