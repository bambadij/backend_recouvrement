"""Classement IA des dossiers de recouvrement.

Le partage des roles est strict : Python calcule les faits (anciennete, taux
regle, comptages), le modele ne fait que juger. Il ne recompte rien, n'invente
aucun chiffre, et son verdict est reproductible tant que les faits ne bougent
pas — c'est ce qui evite qu'un dossier change de couleur d'un affichage a
l'autre.
"""

import json
import logging

import anthropic

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.segmentation.models import PotentielRecouvrement, SegmentRisque
from app.segmentation.schemas import FaitsDossier

logger = logging.getLogger(__name__)

#: Dossiers par appel. Assez large pour amortir le prompt systeme, assez court
#: pour que la sortie structuree tienne dans MAX_TOKENS sans etre tronquee.
TAILLE_LOT = 25

MAX_TOKENS = 8000

SYSTEM = """Tu classes des dossiers de recouvrement de creances pour un cabinet senegalais.

On te fournit, pour chaque dossier, des faits deja calcules. Tu ne recalcules rien
et tu n'inventes aucune donnee absente.

Tu produis deux jugements independants par dossier :

1. « segment » — le risque de non-recouvrement :
   - FAIBLE : paie ou a paye, retard court, engagements tenus.
   - MOYEN : retard installe mais dialogue maintenu, paiements partiels.
   - ELEVE : retard long, relances sans effet, promesses rompues.
   - CRITIQUE : aucun paiement, aucun retour, anciennete extreme, ou litige.

2. « potentiel » — la chance d'aboutir si un agent travaille le dossier
   maintenant : FORT, MOYEN ou FAIBLE. Ce n'est pas l'inverse du risque : un
   dossier CRITIQUE est souvent celui ou l'effort rapporte le moins, et un
   dossier MOYEN avec un debiteur joignable peut avoir un potentiel FORT.

Regles absolues :
- Justifie chaque classement en une phrase, en citant les faits fournis
  (montants, jours de retard, nombre de relances, promesses rompues).
- N'ecris jamais de pourcentage ni de score chiffre : l'echelle est ordinale.
- Classe exactement les dossiers fournis, une entree par creance_id, sans en
  omettre ni en ajouter.
"""

SCHEMA_CLASSEMENT = {
    "type": "object",
    "properties": {
        "dossiers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "creance_id": {"type": "integer"},
                    "segment": {"enum": [s.value for s in SegmentRisque]},
                    "potentiel": {"enum": [p.value for p in PotentielRecouvrement]},
                    "justification": {"type": "string"},
                },
                "required": ["creance_id", "segment", "potentiel", "justification"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["dossiers"],
    "additionalProperties": False,
}


class ClassementDossier:
    """Verdict du modele pour un dossier. Volontairement pauvre : pas de chiffre."""

    __slots__ = ("creance_id", "segment", "potentiel", "justification")

    def __init__(
        self,
        creance_id: int,
        segment: SegmentRisque,
        potentiel: PotentielRecouvrement,
        justification: str,
    ) -> None:
        self.creance_id = creance_id
        self.segment = segment
        self.potentiel = potentiel
        self.justification = justification


class ClassificationIA:
    """Appelle Claude pour classer des lots de dossiers.

    Meme forme que RedactionService : instance unique, client paresseux, erreurs
    traduites en BadRequestException pour que l'interface propose un repli.
    """

    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def disponible(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _obtenir_client(self) -> anthropic.AsyncAnthropic:
        if not self.disponible:
            raise BadRequestException(
                "La segmentation assistee n'est pas configuree sur ce serveur "
                "(ANTHROPIC_API_KEY absente)."
            )
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    @staticmethod
    def _rendu_faits(faits: list[FaitsDossier]) -> str:
        """Les faits en JSON compact : le modele lit mieux une structure qu'une prose."""
        return json.dumps(
            [f.model_dump(mode="json") for f in faits], ensure_ascii=False, indent=1
        )

    async def classer(self, faits: list[FaitsDossier]) -> tuple[list[ClassementDossier], str]:
        """Classe tous les dossiers, par lots. Renvoie (classements, modele)."""
        client = self._obtenir_client()
        classements: list[ClassementDossier] = []
        modele = settings.anthropic_model

        for debut in range(0, len(faits), TAILLE_LOT):
            lot = faits[debut : debut + TAILLE_LOT]
            lot_classe, modele = await self._classer_lot(client, lot)
            classements.extend(lot_classe)

        return classements, modele

    async def _classer_lot(
        self, client: anthropic.AsyncAnthropic, lot: list[FaitsDossier]
    ) -> tuple[list[ClassementDossier], str]:
        try:
            reponse = await client.beta.messages.create(
                model=settings.anthropic_model,
                max_tokens=MAX_TOKENS,
                # Le raisonnement porte sur un jugement borne a partir de faits deja
                # calcules : un effort modere suffit et tient le cout d'une passe
                # sur plusieurs centaines de dossiers.
                output_config={
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": SCHEMA_CLASSEMENT},
                },
                system=SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Classe les dossiers suivants.\n\n" + self._rendu_faits(lot)
                        ),
                    }
                ],
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            logger.warning("Segmentation indisponible : %s", e)
            raise BadRequestException(
                "La segmentation assistee est momentanement indisponible. Reessayez plus tard."
            ) from e
        except anthropic.APIConnectionError as e:
            logger.warning("Segmentation injoignable : %s", e)
            raise BadRequestException("Le service de segmentation est injoignable.") from e

        if reponse.stop_reason == "refusal":
            raise BadRequestException("La segmentation assistee a refuse ce lot de dossiers.")
        if reponse.stop_reason == "max_tokens":
            # Sortie tronquee : le JSON serait invalide. Mieux vaut le dire que
            # de classer la moitie du lot en silence.
            raise BadRequestException(
                "La segmentation a depasse la taille de reponse autorisee sur un lot."
            )

        texte = "".join(bloc.text for bloc in reponse.content if bloc.type == "text").strip()
        if not texte:
            raise BadRequestException("La segmentation assistee n'a produit aucun resultat.")

        return self._interpreter(texte, lot), reponse.model

    @staticmethod
    def _interpreter(texte: str, lot: list[FaitsDossier]) -> list[ClassementDossier]:
        """Convertit la sortie du modele, en ecartant ce qui ne correspond pas au lot.

        Le schema garantit la forme, pas le contenu : un creance_id hors lot ou en
        double serait ecrit sur le mauvais dossier. On filtre plutot que de faire
        confiance.
        """
        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError as e:
            raise BadRequestException("La segmentation a renvoye un resultat illisible.") from e

        attendus = {f.creance_id for f in lot}
        vus: set[int] = set()
        classements: list[ClassementDossier] = []

        for entree in donnees.get("dossiers", []):
            creance_id = entree.get("creance_id")
            if creance_id not in attendus or creance_id in vus:
                logger.warning("Classement ignore pour la creance %s (hors lot)", creance_id)
                continue
            vus.add(creance_id)
            classements.append(
                ClassementDossier(
                    creance_id=creance_id,
                    segment=SegmentRisque(entree["segment"]),
                    potentiel=PotentielRecouvrement(entree["potentiel"]),
                    justification=entree["justification"][:600],
                )
            )

        if manquants := attendus - vus:
            logger.warning("%d dossier(s) non classes par le modele", len(manquants))
        return classements


_service = ClassificationIA()


def get_classification_ia() -> ClassificationIA:
    return _service
