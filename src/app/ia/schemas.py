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
