import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.creances.models import Creance


class SegmentRisque(str, enum.Enum):
    """Echelle ordinale a quatre niveaux, volontairement sans score chiffre.

    Un pourcentage donnerait une precision que rien ne calibre : aucun historique
    de dossiers reellement recouvres ne permet aujourd'hui d'entrainer un modele.
    Quatre classes ordonnees se defendent, un « 73 % de risque » non.
    """

    FAIBLE = "FAIBLE"
    MOYEN = "MOYEN"
    ELEVE = "ELEVE"
    CRITIQUE = "CRITIQUE"


class PotentielRecouvrement(str, enum.Enum):
    """Chance d'aboutir si un agent travaille le dossier.

    Deuxieme axe, distinct du risque : un dossier critique est souvent celui ou
    l'effort rapporte le moins. C'est ce champ, croise au montant restant, qui
    donne l'ordre de traitement.
    """

    FORT = "FORT"
    MOYEN = "MOYEN"
    FAIBLE = "FAIBLE"


#: Ordre de traitement : d'abord ce qui a le plus de chances d'aboutir. A
#: potentiel egal, le montant restant tranche. C'est ce tri, et non le risque,
#: qui repond a « travailler en priorite sur les dossiers les plus rentables » :
#: un dossier critique est souvent celui ou l'effort rapporte le moins.
#:
#: Pose ici, au plus pres de l'enum, parce que deux ecrans s'en servent — la
#: page de classement et la file de relance. Duplique, il finirait par diverger
#: et les deux listes se contrediraient sous les yeux de l'agent.
RANG_POTENTIEL = {
    PotentielRecouvrement.FORT: 0,
    PotentielRecouvrement.MOYEN: 1,
    PotentielRecouvrement.FAIBLE: 2,
}


class Segmentation(Base):
    __tablename__ = "segmentations"
    # Une seule segmentation courante par creance : le recalcul ecrase la precedente.
    __table_args__ = (UniqueConstraint("creance_id", name="uq_segmentations_creance"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    organisation_id: Mapped[int] = mapped_column(ForeignKey("organisations.id", ondelete="CASCADE"), index=True)
    creance_id: Mapped[int] = mapped_column(ForeignKey("creances.id", ondelete="CASCADE"), index=True)

    segment: Mapped[SegmentRisque] = mapped_column(Enum(SegmentRisque, name="segment_risque"), index=True)
    potentiel: Mapped[PotentielRecouvrement] = mapped_column(
        Enum(PotentielRecouvrement, name="potentiel_recouvrement"), index=True
    )
    justification: Mapped[str] = mapped_column(String(600))

    # Instantane des faits ayant fonde le classement. Conserve pour que la decision
    # reste auditable : sans cela, un dossier reclasse est inexplicable a posteriori.
    anciennete_jours: Mapped[int] = mapped_column(Integer)
    taux_regle: Mapped[int] = mapped_column(Integer)
    nb_relances: Mapped[int] = mapped_column(Integer)
    nb_promesses_rompues: Mapped[int] = mapped_column(Integer)

    modele: Mapped[str] = mapped_column(String(100))
    calcule_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creance: Mapped["Creance"] = relationship(back_populates="segmentation")
