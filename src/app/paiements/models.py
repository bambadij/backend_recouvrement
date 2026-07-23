import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.creances.models import Creance


class ModePaiement(str, enum.Enum):
    VIREMENT = "VIREMENT"
    CHEQUE = "CHEQUE"
    ESPECES = "ESPECES"
    CARTE = "CARTE"
    PRELEVEMENT = "PRELEVEMENT"


class Paiement(Base):
    __tablename__ = "paiements"

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    creance_id: Mapped[int] = mapped_column(ForeignKey("creances.id", ondelete="CASCADE"), index=True)

    montant: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    date_paiement: Mapped[date] = mapped_column(default=date.today)
    mode_paiement: Mapped[ModePaiement] = mapped_column(Enum(ModePaiement, name="mode_paiement"))
    reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creance: Mapped["Creance"] = relationship(back_populates="paiements")
