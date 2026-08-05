from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.creances.models import Creance


class Debiteur(Base):
    """Celui qui doit de l'argent — personne physique ou morale."""

    __tablename__ = "debiteurs"
    __table_args__ = (UniqueConstraint("organisation_id", "email", name="uq_debiteurs_organisation_email"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    nom: Mapped[str] = mapped_column(String(100))
    prenom: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    telephone: Mapped[str | None] = mapped_column(String(30))
    adresse: Mapped[str | None] = mapped_column(String(255))
    ville: Mapped[str | None] = mapped_column(String(100))
    code_postal: Mapped[str | None] = mapped_column(String(20))
    entreprise: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    creances: Mapped[list["Creance"]] = relationship(back_populates="debiteur", cascade="all, delete-orphan")
