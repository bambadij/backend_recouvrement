import enum
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.clients.models import Client
    from app.creances.models import Creance
    from app.creanciers.models import Creancier
    from app.promesses.models import Promesse
    from app.relances.models import Relance


class TypeDossier(str, enum.Enum):
    EXPORT = "EXPORT"
    LOCAL = "LOCAL"


class ObjectifDossier(str, enum.Enum):
    AMIABLE = "AMIABLE"
    JUDICIAIRE = "JUDICIAIRE"


class StatutDossier(str, enum.Enum):
    OUVERT = "OUVERT"
    LITIGE = "LITIGE"
    CLOS = "CLOS"


class Dossier(Base):
    """Une demande de recouvrement confiee par un client.

    C'est l'unite que le client remet et dont il suit l'avancement : une ecole
    confie en une fois les impayes de trente etudiants, un assureur confie une
    creance a l'export sur un seul debiteur. Le dossier porte donc PLUSIEURS
    debiteurs — c'est ce qui le distingue de la creance, qui n'en a qu'un.

    La reference vient du client, pas de nous : « DT 586 780 », « SOF/TRD/08/2025 ».
    Les formats sont heterogenes et parfois absents, d'ou un champ libre nullable
    plutot qu'une sequence generee.
    """

    __tablename__ = "dossiers"
    __table_args__ = (
        UniqueConstraint("organisation_id", "reference", name="uq_dossiers_organisation_reference"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), index=True)

    # NULL signifie « le creancier est le client ». C'est le cas courant (l'ecole
    # recouvre ses propres impayes) : on evite ainsi de creer un doublon de la
    # meme entite dans deux tables. L'API expose creancier_nom, qui retombe sur le
    # nom du client quand ce champ est vide.
    creancier_id: Mapped[int | None] = mapped_column(ForeignKey("creanciers.id", ondelete="RESTRICT"), index=True)

    #: Reference du client. Nullable : certaines demandes arrivent sans reference.
    reference: Mapped[str | None] = mapped_column(String(100), index=True)
    #: Jour ou la demande a ete confiee, saisi par l'agent — pas la date de saisie.
    date_reception: Mapped[date] = mapped_column(Date, default=date.today)

    type_dossier: Mapped[TypeDossier] = mapped_column(
        Enum(TypeDossier, name="type_dossier"), default=TypeDossier.LOCAL
    )
    objectif: Mapped[ObjectifDossier] = mapped_column(
        Enum(ObjectifDossier, name="objectif_dossier"), default=ObjectifDossier.AMIABLE
    )
    statut: Mapped[StatutDossier] = mapped_column(
        Enum(StatutDossier, name="statut_dossier"), default=StatutDossier.OUVERT, index=True
    )
    notes: Mapped[str | None] = mapped_column(String(2000))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    client: Mapped["Client"] = relationship(back_populates="dossiers")
    creancier: Mapped["Creancier | None"] = relationship(back_populates="dossiers")
    creances: Mapped[list["Creance"]] = relationship(back_populates="dossier")
    relances: Mapped[list["Relance"]] = relationship(back_populates="dossier", cascade="all, delete-orphan")
    promesses: Mapped[list["Promesse"]] = relationship(back_populates="dossier", cascade="all, delete-orphan")
