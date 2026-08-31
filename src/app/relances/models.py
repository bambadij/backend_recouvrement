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


class IssueRelance(str, enum.Enum):
    """Ce que la relance a produit, du meilleur au pire.

    A distinguer du statut, qui ne dit que le sort de l'ENVOI : une relance
    parfaitement envoyee peut n'obtenir aucune reponse. Les quatre valeurs sont
    exclusives et ordonnees ; c'est ce qui permet un taux de reponse par canal.

    NULL n'est pas une cinquieme valeur : il signifie « pas encore annotee »,
    ce qui ne se confond pas avec SANS_REPONSE. Confondre les deux revenait a
    declarer muets tous les debiteurs qu'on n'avait pas encore rappeles.
    """

    A_PROMIS = "A_PROMIS"
    A_REPONDU = "A_REPONDU"
    SANS_REPONSE = "SANS_REPONSE"
    REFUSE = "REFUSE"


#: Issues qui temoignent d'un contact etabli. Un refus est une reponse : le
#: debiteur a repondu, mal, mais il a repondu — le relancer a l'identique ne
#: sert a rien, ce qui est justement ce que la file cherche a savoir.
ISSUES_AVEC_REPONSE = (IssueRelance.A_PROMIS, IssueRelance.A_REPONDU, IssueRelance.REFUSE)


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

    # Ce que la relance a produit. NULL tant que l'agent n'a rien annote — ce
    # qui n'est pas la meme chose que SANS_REPONSE.
    issue: Mapped[IssueRelance | None] = mapped_column(
        Enum(IssueRelance, name="issue_relance"), index=True
    )
    #: La nuance, en toutes lettres. Garde a cote de l'issue et non remplace par
    #: elle : quatre cases ne disent pas « conteste le montant de la facture 3 ».
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
