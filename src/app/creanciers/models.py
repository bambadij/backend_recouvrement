from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.dossiers.models import Dossier


class Creancier(Base):
    """Celui a qui l'argent est du.

    N'existe en tant qu'entite propre que lorsqu'il differe du client : un
    assureur-credit (le client) confie un dossier dont le creancier est
    l'entreprise assuree. Quand l'ecole recouvre ses propres impayes, elle est
    client et creancier a la fois — le dossier laisse alors creancier_id a NULL
    plutot que de dupliquer la meme entite dans deux tables.
    """

    __tablename__ = "creanciers"
    __table_args__ = (UniqueConstraint("organisation_id", "nom", name="uq_creanciers_organisation_nom"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    nom: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    telephone: Mapped[str | None] = mapped_column(String(30))
    adresse: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    dossiers: Mapped[list["Dossier"]] = relationship(back_populates="creancier")
