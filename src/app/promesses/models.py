import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.creances.models import Creance
    from app.relances.models import Relance


class StatutPromesse(str, enum.Enum):
    ATTENDUE = "ATTENDUE"
    TENUE = "TENUE"
    PARTIELLE = "PARTIELLE"
    ROMPUE = "ROMPUE"


class SourcePromesse(str, enum.Enum):
    """D'ou vient la promesse.

    La distinction est structurante : une promesse SAISIE est un fait rapporte par
    l'agent, une promesse INFEREE est une lecture automatique du champ resultat
    d'une relance — donc revocable. La segmentation pondere les deux differemment
    et l'interface doit pouvoir les distinguer.
    """

    SAISIE = "SAISIE"
    INFEREE = "INFEREE"


class Promesse(Base):
    __tablename__ = "promesses"

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    creance_id: Mapped[int] = mapped_column(ForeignKey("creances.id", ondelete="CASCADE"), index=True)
    # La relance d'ou sort l'engagement. Nul si la promesse a ete saisie hors relance
    # (appel entrant du debiteur, passage au guichet).
    relance_id: Mapped[int | None] = mapped_column(ForeignKey("relances.id", ondelete="SET NULL"), index=True)

    #: Jour ou l'engagement a ete obtenu.
    date_promesse: Mapped[date] = mapped_column(Date, default=date.today)
    #: Jour ou le debiteur s'est engage a payer. C'est cette date qui declenche le
    #: controle : au-dela, sans paiement, la promesse bascule en ROMPUE.
    date_echeance_promesse: Mapped[date] = mapped_column(Date, index=True)
    montant_promis: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    statut: Mapped[StatutPromesse] = mapped_column(
        Enum(StatutPromesse, name="statut_promesse"), default=StatutPromesse.ATTENDUE, index=True
    )
    source: Mapped[SourcePromesse] = mapped_column(
        Enum(SourcePromesse, name="source_promesse"), default=SourcePromesse.SAISIE
    )
    commentaire: Mapped[str | None] = mapped_column(String(1000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    creance: Mapped["Creance"] = relationship(back_populates="promesses")
    relance: Mapped["Relance | None"] = relationship(back_populates="promesses")
