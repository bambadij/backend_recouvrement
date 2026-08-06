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
