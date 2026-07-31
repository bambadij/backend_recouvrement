"""Recommandations d'action a l'echelle du portefeuille.

Meme partage des roles que la segmentation : Python calcule, le modele redige.
Les faits transmis sont ceux deja affiches sur le tableau de bord — encours,
DSO, CEI, balance agee, cartographie, promesses, alertes. Le modele ne recalcule
rien et ne peut donc pas contredire ce que l'agent a sous les yeux.

La difference avec les alertes est de nature : une alerte est une regle
deterministe qui constate un fait ; une recommandation arbitre entre plusieurs
faits pour dire par quoi commencer. C'est ce dernier point qu'un modele fait
mieux qu'un seuil.
"""

import json
import logging

import anthropic

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.organisations.schemas import OrganisationStats

logger = logging.getLogger(__name__)

MAX_TOKENS = 4000

SYSTEM = """Tu conseilles le responsable d'un cabinet de recouvrement senegalais.

On te fournit l'etat chiffre de son portefeuille. Tu en tires des actions
concretes, classees par ordre de priorite.

Regles absolues :
- N'utilise que les chiffres fournis. N'en recalcule aucun, n'en invente aucun.
- Chaque recommandation cite le fait qui la motive, avec son chiffre.
- Recommande une action executable cette semaine, pas une orientation
  strategique. « Relancer les 3 dossiers de plus de 90 jours » et non
  « ameliorer le suivi client ».
- Trois a cinq recommandations. Moins s'il n'y a pas matiere : ne remplis pas.
- Si le portefeuille est sain, dis-le, plutot que de fabriquer un probleme.
- Pas de pourcentage de risque ni de score invente : les seules echelles
  disponibles sont celles fournies.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "recommandations": {
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
        }
    },
    "required": ["recommandations"],
    "additionalProperties": False,
}


class RecommandationsIA:
    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def disponible(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _obtenir_client(self) -> anthropic.AsyncAnthropic:
        if not self.disponible:
            raise BadRequestException(
                "Les recommandations ne sont pas configurees sur ce serveur "
                "(ANTHROPIC_API_KEY absente)."
            )
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    @staticmethod
    def _faits(stats: OrganisationStats) -> str:
        """L'etat du portefeuille, reduit a ce qui fonde une decision.

        On ne transmet pas l'objet complet : l'historique de balance agee et les
        series mensuelles gonfleraient le prompt sans changer l'arbitrage.
        """
        e = stats.efficacite
        faits = {
            "encours_restant": str(stats.montant_total_restant),
            "montant_encaisse": str(stats.montant_total_encaisse),
            "nb_creances": stats.nb_creances,
            "creances_par_statut": stats.creances_par_statut,
            "dso_jours": e.dso,
            "delai_moyen_encaissement_jours": e.delai_moyen,
            "cei_pourcent": e.cei,
            "balance_agee": {t.tranche: str(t.montant) for t in stats.balance_agee},
            "cartographie_risques": [
                {
                    "segment": c.segment,
                    "potentiel": c.potentiel,
                    "nb": c.nb_creances,
                    "montant": str(c.montant),
                }
                for c in stats.cartographie_risques
            ],
            "promesses": {
                "attendues": stats.promesses.nb_attendues,
                "tenues": stats.promesses.nb_tenues,
                "partielles": stats.promesses.nb_partielles,
                "rompues": stats.promesses.nb_rompues,
                "taux_tenue_pourcent": stats.promesses.taux_tenue,
            },
            "alertes": [{"titre": a.titre, "severite": a.severite} for a in stats.alertes],
            "top_debiteurs": [
                {"nom": d.libelle, "montant": str(d.montant), "nb": d.nombre}
                for d in stats.top_debiteurs
            ],
        }
        return json.dumps(faits, ensure_ascii=False, indent=1)

    async def generer(self, stats: OrganisationStats) -> tuple[list[dict], str]:
        """Renvoie (recommandations, modele)."""
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
                            "Voici l'etat du portefeuille. Que dois-je faire en priorite "
                            "cette semaine ?\n\n" + self._faits(stats)
                        ),
                    }
                ],
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            logger.warning("Recommandations indisponibles : %s", e)
            raise BadRequestException(
                "Les recommandations sont momentanement indisponibles."
            ) from e
        except anthropic.APIConnectionError as e:
            logger.warning("Recommandations injoignables : %s", e)
            raise BadRequestException("Le service de recommandations est injoignable.") from e

        if reponse.stop_reason == "refusal":
            raise BadRequestException("Les recommandations ont ete refusees pour ce portefeuille.")
        if reponse.stop_reason == "max_tokens":
            raise BadRequestException("Les recommandations ont depasse la taille autorisee.")

        texte = "".join(b.text for b in reponse.content if b.type == "text").strip()
        if not texte:
            raise BadRequestException("Aucune recommandation produite.")

        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError as e:
            raise BadRequestException("Recommandations illisibles.") from e

        return donnees.get("recommandations", []), reponse.model


_service = RecommandationsIA()


def get_recommandations_ia() -> RecommandationsIA:
    return _service
