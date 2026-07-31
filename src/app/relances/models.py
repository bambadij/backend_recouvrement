import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.creances.models import Creance


class TypeRelance(str, enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    APPEL = "APPEL"
    COURRIER = "COURRIER"
    MISE_EN_DEMEURE = "MISE_EN_DEMEURE"


class StatutRelance(str, enum.Enum):
    PLANIFIEE = "PLANIFIEE"
    ENVOYEE = "ENVOYEE"
    ECHOUEE = "ECHOUEE"


class Relance(Base):
    __tablename__ = "relances"

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    creance_id: Mapped[int] = mapped_column(ForeignKey("creances.id", ondelete="CASCADE"), index=True)

    type_relance: Mapped[TypeRelance] = mapped_column(Enum(TypeRelance, name="type_relance"))
    date_relance: Mapped[date] = mapped_column(default=date.today)
    statut: Mapped[StatutRelance] = mapped_column(
        Enum(StatutRelance, name="statut_relance"), default=StatutRelance.PLANIFIEE
    )
    contenu: Mapped[str | None] = mapped_column(String(2000))
    resultat: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creance: Mapped["Creance"] = relationship(back_populates="relances")
