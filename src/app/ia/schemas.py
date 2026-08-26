import enum
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.relances.models import TypeRelance


class MessageRelanceRequest(BaseModel):
    """Demande de redaction d'un message de relance pour une creance."""

    #: Registre souhaite. Les memes valeurs que les puces de l'interface, pour que
    #: le repli local et la redaction assistee restent interchangeables.
    ton: str | None = Field(default=None, max_length=40)
    #: Consigne libre de l'agent (« insiste sur l'echeancier », « plus court »...).
    instruction: str | None = Field(default=None, max_length=500)


class MessageRelanceResponse(BaseModel):
    message: str
    #: Modele ayant produit le texte, pour tracer ce qui a ete genere par quoi.
    modele: str


class TourAssistant(BaseModel):
    """Un tour de la conversation, tel que l'interface le detient."""

    role: Literal["user", "assistant"]
    contenu: str = Field(min_length=1, max_length=4000)


class AssistantRequest(BaseModel):
    """Question posee a l'assistant sur une creance.

    L'historique voyage avec la requete : rien n'est stocke cote serveur. Une
    question de travail sur un dossier n'a pas a survivre a la fermeture du
    panneau, et la conserver reviendrait a archiver des echanges internes sans
    que personne l'ait demande.
    """

    echanges: list[TourAssistant] = Field(min_length=1, max_length=40)


class AssistantResponse(BaseModel):
    reponse: str
    #: Ce sur quoi la reponse s'appuie, en clair : « 9 relances email, 4 appels ».
    #: Calcule en Python, jamais par le modele — c'est ce qui rend l'avis verifiable.
    appuis: list[str]
    modele: str


class AjustementBrouillon(str, enum.Enum):
    """Les retouches proposees a l'agent, en clair plutot qu'en texte libre.

    Des pastilles et non un champ vide : l'agent qui ouvre l'assistant sait ce
    qu'il veut changer — le ton, la longueur, le canal — mais pas comment le
    demander. Une valeur fermee donne aussi au modele une consigne stable, la
    ou « rends-le plus direct stp » varie a chaque frappe.
    """

    PLUS_FERME = "PLUS_FERME"
    PLUS_COURT = "PLUS_COURT"
    ECHEANCIER = "ECHEANCIER"
    POUR_SMS = "POUR_SMS"
    EN_ANGLAIS = "EN_ANGLAIS"


class BrouillonRequest(BaseModel):
    """Demande de brouillon. Tout est facultatif : l'ouverture n'envoie rien."""

    ajustement: AjustementBrouillon | None = None
    #: Canal impose par l'agent, qui prime alors sur la regle de deduction.
    canal: TypeRelance | None = None
    #: Nombre de mensualites, quand l'ajustement demande un echeancier.
    mensualites: int = Field(default=3, ge=2, le=12)


class EcheanceProposee(BaseModel):
    numero: int
    date_echeance: date
    montant: Decimal


class BrouillonRelance(BaseModel):
    """Le message pret a partir, et de quoi le verifier.

    Le canal et l'echeancier sont calcules en Python ; seul `texte` sort du
    modele. C'est ce partage qui permet a l'agent de contredire la proposition
    sans avoir a relire toute la phrase.
    """

    canal: TypeRelance
    #: La regle qui a choisi ce canal, en toutes lettres.
    canal_raison: str
    texte: str
    #: Le plan de reglement, quand il a ete demande. Vide sinon.
    echeancier: list[EcheanceProposee] = Field(default_factory=list)
    appuis: list[str]
    modele: str
