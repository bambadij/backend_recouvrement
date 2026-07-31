import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.clients.models import Client
    from app.paiements.models import Paiement
    from app.promesses.models import Promesse
    from app.relances.models import Relance
    from app.segmentation.models import Segmentation


class StatutCreance(str, enum.Enum):
    EN_COURS = "EN_COURS"
    EN_RETARD = "EN_RETARD"
    SOLDEE = "SOLDEE"
    LITIGE = "LITIGE"
    ANNULEE = "ANNULEE"


class Creance(Base):
    __tablename__ = "creances"
    __table_args__ = (UniqueConstraint("organisation_id", "reference", name="uq_creances_organisation_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    reference: Mapped[str] = mapped_column(String(50), index=True)
    description: Mapped[str | None] = mapped_column(String(1000))

    # Contexte du dossier, alimente par l'import Excel. Indexes : ce sont les axes
    # de segmentation, donc les filtres de liste les plus frequents.
    # Le financeur n'est pas le debiteur : il designe qui doit effectivement payer
    # (famille, bourse, entreprise, ONG), ce qui change la strategie de relance.
    etablissement: Mapped[str | None] = mapped_column(String(255), index=True)
    cycle: Mapped[str | None] = mapped_column(String(100), index=True)
    financeur: Mapped[str | None] = mapped_column(String(255), index=True)

    montant_initial: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    montant_restant: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    date_creation: Mapped[date] = mapped_column(default=date.today)
    date_echeance: Mapped[date]

    statut: Mapped[StatutCreance] = mapped_column(
        Enum(StatutCreance, name="statut_creance"), default=StatutCreance.EN_COURS
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="creances")
    paiements: Mapped[list["Paiement"]] = relationship(back_populates="creance", cascade="all, delete-orphan")
    relances: Mapped[list["Relance"]] = relationship(back_populates="creance", cascade="all, delete-orphan")
    promesses: Mapped[list["Promesse"]] = relationship(back_populates="creance", cascade="all, delete-orphan")
    segmentation: Mapped["Segmentation | None"] = relationship(
        back_populates="creance", cascade="all, delete-orphan", uselist=False
    )
