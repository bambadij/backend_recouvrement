from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class ClientBase(BaseModel):
    nom: str
    email: EmailStr | None = None
    telephone: str | None = None
    adresse: str | None = None
    notes: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    nom: str | None = None
    email: EmailStr | None = None
    telephone: str | None = None
    adresse: str | None = None
    notes: str | None = None


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    #: Vrai pour le client representant l'organisation elle-meme.
    is_interne: bool
    created_at: datetime
    updated_at: datetime
