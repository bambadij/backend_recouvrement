from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.dossiers.models import Dossier


class Client(Base):
    """Celui qui confie des dossiers a recouvrer.

    C'est votre interlocuteur : l'etablissement scolaire qui vous remet les
    impayes de ses etudiants, la pharmacie, ou un intermediaire comme un
    assureur-credit qui mandate pour le compte de son assure.

    A ne pas confondre avec le creancier, a qui l'argent est du. Les deux sont
    souvent la meme entite — l'ecole est a la fois cliente et creanciere — mais
    pas toujours : un assureur confie un dossier dont le creancier est l'entreprise
    qu'il assure.
    """

    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("organisation_id", "nom", name="uq_clients_organisation_nom"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    nom: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    telephone: Mapped[str | None] = mapped_column(String(30))
    adresse: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(1000))

    # Vrai pour le client qui represente l'organisation elle-meme : le cas de
    # l'organisation qui recouvre ses propres impayes sans donneur d'ordre tiers.
    is_interne: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    dossiers: Mapped[list["Dossier"]] = relationship(back_populates="client")
