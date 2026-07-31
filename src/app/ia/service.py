import logging

import anthropic

from app.clients.models import Client
from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.creances.models import Creance
from app.ia.schemas import MessageRelanceRequest
from app.organisations.models import Organisation
from app.relances.models import Relance
from app.users.models import User

logger = logging.getLogger(__name__)

#: Court : un message de relance fait quelques lignes. La marge couvre le
#: raisonnement, qui est actif par defaut sur ce modele et compte dans max_tokens.
MAX_TOKENS = 2000

SYSTEM = """Tu rediges des messages de relance pour un cabinet de recouvrement senegalais.

Regles absolues :
- Ecris en francais, en vouvoyant, ton professionnel et courtois meme quand le message est ferme.
- N'invente aucun fait : n'utilise que les montants, dates et echanges fournis.
- Ne promets rien au nom du cabinet (pas de remise, pas de delai non demande).
- Ne menace pas de poursuites sauf si le ton demande est « mise en demeure ».
- Rends uniquement le corps du message, sans objet et sans en-tete.
- Termine par une formule de politesse suivie du nom de l'agent en charge, puis du
  nom du cabinet s'il est fourni. Si l'agent n'est pas fourni, ne signe pas.
- Sois bref : le destinataire doit comprendre en un coup d'oeil combien il doit et pour quand.
"""


class RedactionService:
    """Redaction assistee des messages de relance.

    Le service est volontairement sans etat : chaque appel reconstruit le contexte
    depuis la base. L'appel part du backend et non du navigateur — une cle d'API
    dans le front serait lisible par quiconque ouvre les outils de developpement.
    """

    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def disponible(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _obtenir_client(self) -> anthropic.AsyncAnthropic:
        if not self.disponible:
            raise BadRequestException(
                "La redaction assistee n'est pas configuree sur ce serveur. "
                "Utilisez les modeles de message proposes dans le formulaire."
            )
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    @staticmethod
    def _contexte(
        creance: Creance,
        client: Client | None,
        relances: list[Relance],
        agent: User | None,
        organisation: Organisation | None,
    ) -> str:
        """Le dossier mis a plat, en texte, pour le modele.

        Seuls des faits : ce qui n'est pas dans ce bloc ne doit pas apparaitre dans
        le message rendu — la signature comprise, d'ou l'agent et le cabinet ici.
        """
        nom = f"{client.prenom} {client.nom}".strip() if client else "le debiteur"
        lignes = [
            f"Debiteur : {nom}",
            f"Reference de la creance : {creance.reference}",
            f"Montant restant du : {creance.montant_restant} FCFA",
            f"Montant initial : {creance.montant_initial} FCFA",
            f"Echeance : {creance.date_echeance.isoformat()}",
            f"Statut : {creance.statut.value}",
        ]
        if client and client.entreprise:
            lignes.append(f"Entreprise : {client.entreprise}")
        if agent:
            lignes.append(f"Agent en charge, signataire du message : {agent.prenom} {agent.nom}".rstrip())
        if organisation:
            lignes.append(f"Cabinet expediteur : {organisation.nom}")

        if relances:
            lignes.append("")
            lignes.append("Historique des relances, de la plus ancienne a la plus recente :")
            for r in relances[-8:]:
                detail = f"- {r.date_relance.isoformat()} : {r.type_relance.value}, {r.statut.value}"
                if r.resultat:
                    detail += f" — retour du debiteur : {r.resultat}"
                lignes.append(detail)
        else:
            lignes.append("")
            lignes.append("Aucune relance n'a encore ete envoyee sur ce dossier.")
        return "\n".join(lignes)

    async def generer_message(
        self,
        creance: Creance,
        client: Client | None,
        relances: list[Relance],
        demande: MessageRelanceRequest,
        agent: User | None = None,
        organisation: Organisation | None = None,
    ) -> tuple[str, str]:
        """Renvoie (message, modele). Leve BadRequestException si la redaction echoue."""
        anthropic_client = self._obtenir_client()

        consignes = [self._contexte(creance, client, relances, agent, organisation), ""]
        if demande.ton:
            consignes.append(f"Registre demande : {demande.ton}.")
        if demande.instruction:
            consignes.append(f"Consigne de l'agent : {demande.instruction}")
        consignes.append("Redige le message de relance.")

        try:
            reponse = await anthropic_client.beta.messages.create(
                model=settings.anthropic_model,
                max_tokens=MAX_TOKENS,
                # Une relance est une tache courte et cadree : effort faible suffit,
                # et c'est ce qui tient la latence du bouton sous la seconde.
                output_config={"effort": "low"},
                system=SYSTEM,
                messages=[{"role": "user", "content": "\n".join(consignes)}],
                # Les classificateurs de surete peuvent decliner une demande. Le repli
                # serveur rejoue la requete sur un autre modele dans le meme appel.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            logger.warning("Redaction assistee indisponible : %s", e)
            raise BadRequestException(
                "La redaction assistee est momentanement indisponible. "
                "Utilisez les modeles de message proposes dans le formulaire."
            ) from e
        except anthropic.APIConnectionError as e:
            logger.warning("Redaction assistee injoignable : %s", e)
            raise BadRequestException(
                "Le service de redaction est injoignable. "
                "Utilisez les modeles de message proposes dans le formulaire."
            ) from e

        # A verifier AVANT de lire le contenu : sur un refus, content est vide ou partiel.
        if reponse.stop_reason == "refusal":
            raise BadRequestException(
                "La redaction assistee a refuse cette demande. Reformulez la consigne "
                "ou utilisez les modeles de message proposes."
            )

        message = "".join(bloc.text for bloc in reponse.content if bloc.type == "text").strip()
        if not message:
            raise BadRequestException("La redaction assistee n'a produit aucun texte.")
        return message, reponse.model
