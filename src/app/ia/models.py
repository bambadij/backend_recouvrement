from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AppelIA(Base):
    """Un appel de modele, et ce qu'il a coute.

    Ecrit apres coup, jamais lu par le metier : cette table sert a mesurer, pas
    a decider. Rien dans l'application ne doit se mettre a en dependre — un
    quota qui bloquerait une relance parce qu'une ligne de journal manque
    ferait echouer le travail pour une raison comptable.
    """

    __tablename__ = "appels_ia"

    id: Mapped[int] = mapped_column(primary_key=True)

    #: Quelle fonction a appele : « brouillon », « assistant_creance »,
    #: « analyse_dossier », « segmentation »... Une chaine et non un enum : de
    #: nouvelles fonctions apparaitront, et une migration d'enum pour chacune
    #: freinerait justement ce qu'on cherche a observer.
    fonction: Mapped[str] = mapped_column(String(60), index=True)
    modele: Mapped[str] = mapped_column(String(80))

    #: Nulle pour un super-administrateur, qui n'appartient a aucune
    #: organisation. SET NULL a la suppression : la consommation passee reste
    #: vraie meme si l'organisation disparait.
    organisation_id: Mapped[int | None] = mapped_column(
        ForeignKey("organisations.id", ondelete="SET NULL"), index=True
    )
    #: Instantane du nom, comme Paiement.saisi_par_nom : la consommation passee
    #: ne doit pas changer si un compte est renomme ou supprime.
    agent_nom: Mapped[str | None] = mapped_column(String(200))

    #: Nuls quand l'appel a echoue avant d'obtenir une reponse.
    jetons_entree: Mapped[int | None] = mapped_column(Integer)
    jetons_sortie: Mapped[int | None] = mapped_column(Integer)
    duree_ms: Mapped[int] = mapped_column(Integer)

    #: Le message d'echec, tronque. Nul quand l'appel a abouti.
    erreur: Mapped[str | None] = mapped_column(String(300))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
