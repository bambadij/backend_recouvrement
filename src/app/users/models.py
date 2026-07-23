import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.organisations.models import Organisation


class RoleUtilisateur(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    AGENT = "AGENT"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[RoleUtilisateur] = mapped_column(
        Enum(RoleUtilisateur, name="role_utilisateur"), default=RoleUtilisateur.AGENT
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Null uniquement pour le SUPER_ADMIN (transverse a toutes les organisations).
    organisation_id: Mapped[int | None] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organisation: Mapped["Organisation | None"] = relationship(back_populates="users")
