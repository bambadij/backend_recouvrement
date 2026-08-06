import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.debiteurs.models import Debiteur
    from app.dossiers.models import Dossier
    from app.promesses.models import Promesse


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
    # La relance vise un debiteur A L'INTERIEUR d'un dossier. Un dossier peut en
    # contenir trente (les etudiants d'une ecole) : on ne relance pas « le
    # dossier ». Mais on ne relance pas non plus facture par facture — un seul
    # courrier couvre tous les impayes de ce debiteur dans ce dossier.
    dossier_id: Mapped[int] = mapped_column(ForeignKey("dossiers.id", ondelete="CASCADE"), index=True)
    debiteur_id: Mapped[int] = mapped_column(ForeignKey("debiteurs.id", ondelete="CASCADE"), index=True)

    type_relance: Mapped[TypeRelance] = mapped_column(Enum(TypeRelance, name="type_relance"))
    date_relance: Mapped[date] = mapped_column(default=date.today)
    statut: Mapped[StatutRelance] = mapped_column(
        Enum(StatutRelance, name="statut_relance"), default=StatutRelance.PLANIFIEE
    )
    contenu: Mapped[str | None] = mapped_column(String(2000))
    resultat: Mapped[str | None] = mapped_column(String(1000))

    # Nom de l'agent ayant emis la relance, fige au moment de l'emission — meme
    # convention que Paiement.saisi_par_nom. Un instantane plutot qu'une cle
    # etrangere : la productivite passee ne doit pas changer si un compte est
    # renomme ou supprime. Nul sur les relances anterieures a ce champ.
    cree_par_nom: Mapped[str | None] = mapped_column(String(200), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dossier: Mapped["Dossier"] = relationship(back_populates="relances")
    debiteur: Mapped["Debiteur"] = relationship(back_populates="relances")
    promesses: Mapped[list["Promesse"]] = relationship(back_populates="relance")
