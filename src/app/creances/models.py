import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.debiteurs.models import Debiteur
    from app.paiements.models import Paiement
    from app.relances.models import Relance


class StatutCreance(str, enum.Enum):
    EN_COURS = "EN_COURS"
    EN_RETARD = "EN_RETARD"
    SOLDEE = "SOLDEE"
    LITIGE = "LITIGE"
    ANNULEE = "ANNULEE"


class Creance(Base):
    """La dette elle-meme : ce qu'un debiteur doit."""

    __tablename__ = "creances"
    __table_args__ = (UniqueConstraint("organisation_id", "reference", name="uq_creances_organisation_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    debiteur_id: Mapped[int] = mapped_column(ForeignKey("debiteurs.id", ondelete="CASCADE"), index=True)

    # Reference interne, generee par l'application et unique par organisation.
    reference: Mapped[str] = mapped_column(String(50), index=True)
    # Numero de la facture d'origine, tel qu'emis par le creancier (facultatif :
    # absent des reprises de stock ou des creances non facturees).
    numero_facture: Mapped[str | None] = mapped_column(String(50), index=True)
    description: Mapped[str | None] = mapped_column(String(1000))

    montant_initial: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    montant_restant: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    # date_facture : date d'emission de la facture — fait foi pour l'anciennete,
    # les interets de retard et la prescription. Ne pas confondre avec date_saisie,
    # qui est la date d'entree de la creance dans l'outil.
    date_facture: Mapped[date | None]
    date_saisie: Mapped[date] = mapped_column(default=date.today)
    date_echeance: Mapped[date]

    statut: Mapped[StatutCreance] = mapped_column(
        Enum(StatutCreance, name="statut_creance"), default=StatutCreance.EN_COURS
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    debiteur: Mapped["Debiteur"] = relationship(back_populates="creances")
    paiements: Mapped[list["Paiement"]] = relationship(back_populates="creance", cascade="all, delete-orphan")
    relances: Mapped[list["Relance"]] = relationship(back_populates="creance", cascade="all, delete-orphan")
