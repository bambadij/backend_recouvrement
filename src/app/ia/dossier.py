"""Analyse d'un dossier de recouvrement.

Meme partage des roles que la segmentation et les recommandations : Python
calcule, le modele redige. Les faits transmis sont ceux que l'interface affiche
deja — encours, balance agee, encours par debiteur, relances, promesses. Le
modele ne recalcule rien et ne peut donc pas contredire ce que l'agent a sous
les yeux.

La difference avec les recommandations du tableau de bord est la portee : celles
la arbitrent entre tous les dossiers, celle ci travaille l'interieur d'un seul —
sur quel debiteur concentrer l'effort, quelle facture sortir de la routine.
"""

import json
import logging

import anthropic

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.dossiers.schemas import FaitsDossier

logger = logging.getLogger(__name__)

MAX_TOKENS = 3000

SYSTEM = """Tu analyses un dossier de recouvrement pour un cabinet senegalais.

Un dossier est une demande confiee par un client : il porte plusieurs debiteurs
et plusieurs factures. On te fournit son etat chiffre.

Regles absolues :
- N'utilise que les chiffres fournis. N'en recalcule aucun, n'en invente aucun.
- La synthese fait trois a quatre phrases : ou en est ce dossier, et pourquoi.
- Chaque action cite le fait qui la motive, avec son chiffre.
- Recommande une action executable cette semaine, et nomme le debiteur concerne
  quand elle en vise un. « Appeler Atlantique Negoce, 4,2 M restants et une
  promesse rompue » et non « ameliorer le suivi ».
- Deux a quatre actions. Moins s'il n'y a pas matiere : ne remplis pas.
- Si le dossier est sain ou solde, dis-le, plutot que de fabriquer un probleme.
- Pas de pourcentage de risque ni de score invente.
- Ecris en francais, sobre, sans formule commerciale.

Trois graphiques sont affiches a cote de ton texte. Ecris la legende de chacun
dans « lectures » : une phrase, deux au plus, qui dit ce que la forme du graphe
signifie pour le recouvrement — pas ce qu'elle montre, que l'agent voit deja.
- anciennete : la balance agee, tranche par tranche.
- debiteurs : l'encours de chaque debiteur.
- engagements : les promesses tenues, attendues et rompues.
Chaque legende cite un chiffre de SON graphique. Laisse la chaine vide quand le
graphique correspondant n'a rien a montrer — aucune promesse, aucun impaye.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "synthese": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "titre": {"type": "string"},
                    "action": {"type": "string"},
                    "fait_declencheur": {"type": "string"},
                    "urgence": {"enum": ["haute", "moyenne", "basse"]},
                },
                "required": ["titre", "action", "fait_declencheur", "urgence"],
                "additionalProperties": False,
            },
        },
        "lectures": {
            "type": "object",
            "properties": {
                "anciennete": {"type": "string"},
                "debiteurs": {"type": "string"},
                "engagements": {"type": "string"},
            },
            "required": ["anciennete", "debiteurs", "engagements"],
            "additionalProperties": False,
        },
    },
    "required": ["synthese", "actions", "lectures"],
    "additionalProperties": False,
}


class AnalyseDossierIA:
    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def disponible(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _obtenir_client(self) -> anthropic.AsyncAnthropic:
        if not self.disponible:
            raise BadRequestException(
                "L'analyse de dossier n'est pas configuree sur ce serveur (ANTHROPIC_API_KEY absente)."
            )
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    @staticmethod
    def _faits(faits: FaitsDossier) -> str:
        # Les Decimal passent en chaine : json.dumps ne les serialise pas, et les
        # convertir en float introduirait des arrondis sur des montants.
        return json.dumps(faits.model_dump(mode="json"), ensure_ascii=False, indent=1)

    async def analyser(self, faits: FaitsDossier) -> tuple[str, list[dict], dict, str]:
        """Renvoie (synthese, actions, lectures, modele)."""
        client = self._obtenir_client()

        try:
            reponse = await client.beta.messages.create(
                model=settings.anthropic_model,
                max_tokens=MAX_TOKENS,
                output_config={
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": SCHEMA},
                },
                system=SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            "Voici l'etat de ce dossier. Ou en est-il, et que dois-je "
                            "faire en priorite ?\n\n" + self._faits(faits)
                        ),
                    }
                ],
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            logger.warning("Analyse de dossier indisponible : %s", e)
            raise BadRequestException("L'analyse est momentanement indisponible.") from e
        except anthropic.APIConnectionError as e:
            logger.warning("Analyse de dossier injoignable : %s", e)
            raise BadRequestException("Le service d'analyse est injoignable.") from e

        if reponse.stop_reason == "refusal":
            raise BadRequestException("L'analyse a ete refusee pour ce dossier.")
        if reponse.stop_reason == "max_tokens":
            raise BadRequestException("L'analyse a depasse la taille autorisee.")

        texte = "".join(b.text for b in reponse.content if b.type == "text").strip()
        if not texte:
            raise BadRequestException("Aucune analyse produite.")

        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError as e:
            raise BadRequestException("Analyse illisible.") from e

        return (
            donnees.get("synthese", ""),
            donnees.get("actions", []),
            donnees.get("lectures", {}),
            reponse.model,
        )
