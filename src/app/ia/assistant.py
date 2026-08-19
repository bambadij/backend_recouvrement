"""Assistant conversationnel sur une creance.

Meme partage des roles que partout ailleurs : Python calcule, le modele redige.
On lui transmet l'etat chiffre de la facture et de son debiteur, et il repond
aux questions de l'agent — pourquoi ce debiteur ne paie pas, quel canal tenter,
comment formuler une proposition.

La difference avec la redaction de relance est le destinataire : celle-la ecrit
au debiteur, celui-ci parle a l'agent. Le texte produit ici n'est pas un message
a envoyer tel quel, c'est un avis sur un dossier.
"""

import json
import logging

import anthropic

from app.core.config import settings
from app.core.exceptions import BadRequestException

logger = logging.getLogger(__name__)

MAX_TOKENS = 2000

#: Au-dela, la conversation est tronquee par le debut. Une question posee au
#: dixieme tour porte sur les tours recents, pas sur le premier.
MAX_TOURS = 12

SYSTEM = """Tu assistes un agent de recouvrement senegalais sur une facture impayee.

On te fournit l'etat chiffre de la facture et de son debiteur : montants,
echeance, retard, relances tentees par canal, reponses obtenues, delais de
reglement passes, engagements tenus ou rompus.

Regles absolues :
- N'utilise que les chiffres fournis. N'en recalcule aucun, n'en invente aucun.
- Reponds en trois paragraphes courts au maximum. L'agent est au telephone.
- Appuie chaque affirmation sur un fait transmis, en citant son chiffre.
- Termine par ce qu'il faut faire, concretement, aujourd'hui.
- Quand les faits ne permettent pas de repondre, dis-le. « Aucune relance n'a
  encore ete tentee, je ne peux rien dire de ses habitudes » vaut mieux qu'une
  supposition presentee comme un constat.
- Pas de pourcentage de risque ni de score invente.
- Si l'agent demande un texte a envoyer au debiteur, ecris-le tel qu'il doit
  partir, sans commentaire autour.
- Ecris en francais, sobre, sans formule commerciale.

Le champ « resultat » d'une relance n'est rempli que lorsque le debiteur a
reagi. Si « reponses_tracees » est faux, personne ne remplit ce champ dans ce
cabinet : ne conclus alors rien sur les canaux qui marchent ou pas.
"""

#: Ouverture de la conversation cote creance.
ENTETE_CREANCE = "Voici l'etat de cette facture et de son debiteur."

SYSTEM_PORTEFEUILLE = """Tu assistes un responsable de recouvrement senegalais qui
regarde le tableau de bord de son portefeuille.

On te fournit ce que l'application a calcule : balance agee par tranche
d'anciennete, indicateurs d'efficacite, principaux debiteurs, activite des
agents, alertes deterministes.

Regles absolues :
- N'utilise que les chiffres fournis. N'en recalcule aucun, n'en invente aucun.
- Trois paragraphes courts au maximum, puis ce qu'il faut faire cette semaine.
- Appuie chaque affirmation sur un fait transmis, en citant son chiffre.
- Quand une donnee manque, dis-le plutot que de combler. Un portefeuille jeune
  n'a ni historique mensuel ni promesses : « je ne peux rien dire de la
  tendance » est la bonne reponse, pas une extrapolation.
- Pas de score, pas de projection chiffree, pas de pourcentage invente.
- Ecris en francais, sobre, sans formule commerciale.

Deux pieges de lecture a connaitre :
- Le DSO estime rapporte l'encours au flux confie sur la fenetre : il monte
  quand on confie davantage, meme sans perte d'efficacite. L'ecart avec le
  delai reellement constate se lit ainsi, et non comme une contradiction.
- Le champ « resultat » d'une relance n'est rempli que lorsque le debiteur a
  reagi. Un taux de retour a zero peut signifier que personne ne remplit ce
  champ : ne conclus alors rien sur les canaux.
"""

#: Ouverture de la conversation cote portefeuille.
ENTETE_PORTEFEUILLE = "Voici l'etat chiffre du portefeuille, tel que l'application le calcule."


class AssistantIA:
    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def disponible(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _obtenir_client(self) -> anthropic.AsyncAnthropic:
        if not self.disponible:
            raise BadRequestException(
                "L'assistant n'est pas configure sur ce serveur (ANTHROPIC_API_KEY absente)."
            )
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def repondre(
        self,
        faits: dict,
        echanges: list[dict],
        *,
        system: str = SYSTEM,
        entete: str = ENTETE_CREANCE,
    ) -> tuple[str, str]:
        """Renvoie (reponse, modele).

        `echanges` est la conversation telle que l'interface la detient : c'est
        elle qui porte l'historique, pas le serveur. Rien n'est stocke ici — une
        question posee sur un dossier n'a pas a survivre a la fermeture du
        panneau, et la conserver reviendrait a archiver des echanges de travail
        sans que personne l'ait demande.

        `system` et `entete` changent selon l'echelle de la question — une
        facture ou le portefeuille entier. Le reste est identique : memes
        garde-fous, meme appel, meme refus de produire un chiffre.
        """
        client = self._obtenir_client()

        if not echanges:
            raise BadRequestException("Aucune question posee.")

        # Les faits ouvrent la conversation plutot que d'etre repetes a chaque
        # tour : le modele les garde en contexte, et le cache de prompt les
        # facture une seule fois.
        messages = [
            {
                "role": "user",
                "content": entete + "\n\n" + json.dumps(faits, ensure_ascii=False, indent=1),
            },
            {"role": "assistant", "content": "J'ai lu le dossier. Que voulez-vous savoir ?"},
            *echanges[-MAX_TOURS:],
        ]

        try:
            reponse = await client.beta.messages.create(
                model=settings.anthropic_model,
                max_tokens=MAX_TOKENS,
                output_config={"effort": "medium"},
                system=system,
                messages=messages,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            logger.warning("Assistant indisponible : %s", e)
            raise BadRequestException("L'assistant est momentanement indisponible.") from e
        except anthropic.APIConnectionError as e:
            logger.warning("Assistant injoignable : %s", e)
            raise BadRequestException("Le service d'assistance est injoignable.") from e

        if reponse.stop_reason == "refusal":
            raise BadRequestException("L'assistant a refuse de repondre a cette demande.")

        texte = "".join(b.text for b in reponse.content if b.type == "text").strip()
        if not texte:
            raise BadRequestException("Aucune reponse produite.")

        return texte, reponse.model
