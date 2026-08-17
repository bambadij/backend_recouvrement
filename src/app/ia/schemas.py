from typing import Literal

from pydantic import BaseModel, Field


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
