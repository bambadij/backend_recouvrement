from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.users.models import RoleUtilisateur


class UserCreate(BaseModel):
    nom: str
    prenom: str
    email: EmailStr
    password: str = Field(min_length=8)
    # Utilises uniquement quand le createur est SUPER_ADMIN ; ignores et forces
    # a (AGENT, organisation du createur) quand le createur est ADMIN.
    role: RoleUtilisateur = RoleUtilisateur.AGENT
    organisation_id: int | None = None


class UserUpdate(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    password: str | None = Field(default=None, min_length=8)
    role: RoleUtilisateur | None = None
    organisation_id: int | None = None
    is_active: bool | None = None


class UserSelfUpdate(BaseModel):
    """Champs qu'un utilisateur peut modifier sur SON propre compte.

    Volontairement sans `role`, `organisation_id` ni `is_active` : les exposer ici
    laisserait n'importe quel agent se promouvoir ADMIN ou changer d'organisation.
    Ces champs restent l'apanage de PATCH /users/{id}, garde par CurrentAdminDep.

    Le mot de passe actuel est exige pour en definir un nouveau : un jeton vole
    suffirait sinon a verrouiller le compte de son proprietaire.
    """

    nom: str | None = None
    prenom: str | None = None
    mot_de_passe_actuel: str | None = None
    nouveau_mot_de_passe: str | None = Field(default=None, min_length=8)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str
    email: EmailStr
    role: RoleUtilisateur
    organisation_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
