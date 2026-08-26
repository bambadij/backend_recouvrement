import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class CreancierBase(BaseModel):
    nom: str
    email: EmailStr | None = None
    telephone: str | None = None
    adresse: str | None = None
    notes: str | None = None


class CreancierCreate(CreancierBase):
    pass


class CreancierUpdate(BaseModel):
    nom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None
    adresse: str | None = None
    notes: str | None = None


class CreancierRead(CreancierBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    created_at: datetime
    updated_at: datetime


class OrigineCreancier(str, enum.Enum):
    """D'ou vient la ligne du repertoire.

    La distinction est structurante : une entite PROPRE se modifie et se
    supprime ici, un CLIENT ne s'y touche pas. Une seule fiche par entite, un
    seul endroit pour la corriger — sinon la duplication qu'on evite en base
    revient par l'interface.
    """

    PROPRE = "PROPRE"
    CLIENT = "CLIENT"


class CreancierRepertoire(BaseModel):
    """Un creancier, quelle que soit la table qui le porte."""

    origine: OrigineCreancier
    #: Identifiant dans SA table : creanciers.id ou clients.id selon l'origine.
    #: Les deux espaces d'identifiants ne se melangent pas — l'interface doit
    #: lire « origine » avant d'en faire quoi que ce soit.
    id: int
    nom: str
    email: str | None
    telephone: str | None
    adresse: str | None
    #: Dossiers dont il est effectivement le creancier. Zero est une information :
    #: c'est une fiche creee puis jamais utilisee.
    nb_dossiers: int
