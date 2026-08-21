"""Les pieces d'un dossier : mandat, facture d'origine, recu de paiement.

Un dossier de recouvrement vit avec ses pieces. Quand un debiteur conteste, ce
que l'agent peut lui opposer se trouve la — le bon de livraison signe, la
facture telle qu'elle a ete emise, l'accuse de reception d'une mise en demeure.

Le contenu est stocke EN BASE, en binaire. C'est un choix assume : aucune
infrastructure supplementaire, et la piece est sauvegardee en meme temps que la
donnee qu'elle justifie. Le prix a payer est une base qui grossit et des
restaurations plus lourdes ; deux garde-fous le limitent — un plafond de taille
strict, et une colonne differee pour que lister des documents ne charge jamais
leurs octets.
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String, func
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.creances.models import Creance
    from app.dossiers.models import Dossier
    from app.paiements.models import Paiement


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        # Exactement un rattachement. Une piece flottante n'aurait pas de
        # contexte, et une piece rattachee a deux objets serait ambigue a
        # supprimer : la cascade de l'un effacerait la preuve de l'autre.
        CheckConstraint(
            "(CASE WHEN dossier_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN creance_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN paiement_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_documents_un_seul_rattachement",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(
        ForeignKey("organisations.id", ondelete="CASCADE"), index=True
    )

    dossier_id: Mapped[int | None] = mapped_column(
        ForeignKey("dossiers.id", ondelete="CASCADE"), index=True
    )
    creance_id: Mapped[int | None] = mapped_column(
        ForeignKey("creances.id", ondelete="CASCADE"), index=True
    )
    paiement_id: Mapped[int | None] = mapped_column(
        ForeignKey("paiements.id", ondelete="CASCADE"), index=True
    )

    #: Le nom tel que l'agent l'a depose. Sert a l'affichage et au telechargement,
    #: jamais a construire un chemin : il vient du poste de l'utilisateur.
    nom: Mapped[str] = mapped_column(String(255))
    type_mime: Mapped[str] = mapped_column(String(120))
    taille: Mapped[int] = mapped_column(Integer)

    #: Differe : une liste de pieces affiche des noms et des tailles, pas des
    #: octets. Sans cela, ouvrir un dossier de dix pieces en chargerait le poids
    #: entier en memoire pour n'en montrer aucune.
    contenu: Mapped[bytes] = deferred(mapped_column(LargeBinary))

    #: Qui a depose, fige a l'instant du depot — meme convention que
    #: Paiement.saisi_par_nom : la trace ne doit pas changer si un compte est
    #: renomme ou supprime.
    depose_par_nom: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dossier: Mapped["Dossier | None"] = relationship()
    creance: Mapped["Creance | None"] = relationship()
    paiement: Mapped["Paiement | None"] = relationship()
