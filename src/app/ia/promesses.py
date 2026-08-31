"""Extraction des engagements de paiement depuis les comptes rendus de relance.

Le champ Relance.resultat est du texte libre saisi par l'agent (« rappellera
lundi », « promet 500 000 avant le 15 »). Cette passe le lit et en tire des
promesses datees et chiffrees, exploitables par la segmentation.

C'est de l'inference sur de la saisie humaine, pas une donnee : les promesses
produites ici sont marquees SourcePromesse.INFEREE pour rester distinguables de
celles qu'un agent a saisies lui-meme.
"""

import json
import logging
from datetime import date
from decimal import Decimal

import anthropic

from app.core.config import settings
from app.ia import journal
from app.core.exceptions import BadRequestException
from app.relances.models import Relance

logger = logging.getLogger(__name__)

TAILLE_LOT = 30
MAX_TOKENS = 8000

SYSTEM = """Tu lis des comptes rendus de relance de recouvrement, rediges en francais
par des agents senegalais, et tu en extrais les engagements de paiement.

Un engagement suppose DEUX elements : une intention de payer et une echeance
datable. Sans les deux, il n'y a pas d'engagement.

Comptent comme engagement :
- « promet de payer 500 000 avant le 15 » -> montant et date explicites.
- « reglera la totalite fin du mois » -> montant = solde restant, date = dernier
  jour du mois en cours.
- « versera la moitie la semaine prochaine » -> montant = moitie du solde,
  date = 7 jours apres la relance.

Ne comptent PAS comme engagement :
- « injoignable », « numero errone », « a rappeler » : aucun engagement.
- « conteste la facture », « dit avoir deja paye » : litige, pas promesse.
- « rappellera pour convenir d'une date » : intention sans echeance datable.
- « promet de payer des que possible » : pas d'echeance datable.

Regles absolues :
- N'invente ni montant ni date : deduis-les du texte et des faits fournis
  (solde restant, date de la relance), sinon n'extrais rien.
- Le montant promis ne depasse jamais le solde restant du dossier.
- La date d'echeance promise est posterieure ou egale a la date de la relance.
- Dans le doute, n'extrais pas. Une promesse inventee fausse le classement du
  dossier ; une promesse manquee ne fait que le laisser en l'etat.
"""

SCHEMA_EXTRACTION = {
    "type": "object",
    "properties": {
        "engagements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "relance_id": {"type": "integer"},
                    "date_echeance_promesse": {"type": "string", "format": "date"},
                    "montant_promis": {"type": "number"},
                    "extrait": {"type": "string"},
                },
                "required": [
                    "relance_id",
                    "date_echeance_promesse",
                    "montant_promis",
                    "extrait",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["engagements"],
    "additionalProperties": False,
}


class EngagementExtrait:
    __slots__ = ("relance_id", "date_echeance_promesse", "montant_promis", "extrait")

    def __init__(
        self,
        relance_id: int,
        date_echeance_promesse: date,
        montant_promis: Decimal,
        extrait: str,
    ) -> None:
        self.relance_id = relance_id
        self.date_echeance_promesse = date_echeance_promesse
        self.montant_promis = montant_promis
        self.extrait = extrait


class ExtractionPromessesIA:
    def __init__(self) -> None:
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def disponible(self) -> bool:
        return bool(settings.anthropic_api_key)

    def _obtenir_client(self) -> anthropic.AsyncAnthropic:
        if not self.disponible:
            raise BadRequestException(
                "L'extraction des promesses n'est pas configuree sur ce serveur "
                "(ANTHROPIC_API_KEY absente)."
            )
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        return self._client

    async def extraire(
        self, relances: list[Relance], soldes: dict[int, Decimal]
    ) -> tuple[list[EngagementExtrait], str]:
        """Renvoie (engagements, modele). `soldes` mappe (dossier_id, debiteur_id) -> restant."""
        client = self._obtenir_client()
        engagements: list[EngagementExtrait] = []
        modele = settings.anthropic_model

        for debut in range(0, len(relances), TAILLE_LOT):
            lot = relances[debut : debut + TAILLE_LOT]
            lot_extrait, modele = await self._extraire_lot(client, lot, soldes)
            engagements.extend(lot_extrait)

        return engagements, modele

    @staticmethod
    def _rendu(relances: list[Relance], soldes: dict[int, Decimal]) -> str:
        return json.dumps(
            [
                {
                    "relance_id": r.id,
                    "date_relance": r.date_relance.isoformat(),
                    "canal": r.type_relance.value,
                    "solde_restant_dossier": str(soldes.get((r.dossier_id, r.debiteur_id), 0)),
                    "compte_rendu": r.resultat,
                }
                for r in relances
            ],
            ensure_ascii=False,
            indent=1,
        )

    async def _extraire_lot(
        self,
        client: anthropic.AsyncAnthropic,
        lot: list[Relance],
        soldes: dict[int, Decimal],
    ) -> tuple[list[EngagementExtrait], str]:
        chrono = journal.Chrono()
        try:
            reponse = await client.beta.messages.create(
                model=settings.anthropic_model,
                max_tokens=MAX_TOKENS,
                output_config={
                    "effort": "medium",
                    "format": {"type": "json_schema", "schema": SCHEMA_EXTRACTION},
                },
                system=SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Date du jour : {date.today().isoformat()}.\n"
                            "Extrais les engagements de paiement des comptes rendus suivants.\n\n"
                            + self._rendu(lot, soldes)
                        ),
                    }
                ],
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            logger.warning("Extraction des promesses indisponible : %s", e)
            await journal.enregistrer(
                "extraction_promesses", settings.anthropic_model, chrono, erreur=str(e)[:300]
            )
            raise BadRequestException(
                "L'extraction des promesses est momentanement indisponible."
            ) from e
        except anthropic.APIConnectionError as e:
            logger.warning("Extraction des promesses injoignable : %s", e)
            await journal.enregistrer(
                "extraction_promesses", settings.anthropic_model, chrono, erreur=str(e)[:300]
            )
            raise BadRequestException("Le service d'extraction est injoignable.") from e

        await journal.enregistrer(
            "extraction_promesses", settings.anthropic_model, chrono, reponse=reponse
        )

        if reponse.stop_reason == "refusal":
            raise BadRequestException("L'extraction a refuse ce lot de comptes rendus.")
        if reponse.stop_reason == "max_tokens":
            raise BadRequestException(
                "L'extraction a depasse la taille de reponse autorisee sur un lot."
            )

        texte = "".join(bloc.text for bloc in reponse.content if bloc.type == "text").strip()
        if not texte:
            return [], reponse.model

        return self._interpreter(texte, lot, soldes), reponse.model

    @staticmethod
    def _interpreter(
        texte: str, lot: list[Relance], soldes: dict[int, Decimal]
    ) -> list[EngagementExtrait]:
        """Valide les extractions contre les faits avant de les accepter.

        Le schema garantit la forme, pas la coherence : on rejette ici ce que le
        modele aurait pu deduire de travers (date anterieure a la relance, montant
        superieur au solde), plutot que d'ecrire une promesse fausse en base.
        """
        try:
            donnees = json.loads(texte)
        except json.JSONDecodeError as e:
            raise BadRequestException("L'extraction a renvoye un resultat illisible.") from e

        relances_par_id = {r.id: r for r in lot}
        engagements: list[EngagementExtrait] = []

        for entree in donnees.get("engagements", []):
            relance = relances_par_id.get(entree.get("relance_id"))
            if relance is None:
                continue

            try:
                echeance = date.fromisoformat(entree["date_echeance_promesse"])
                montant = Decimal(str(entree["montant_promis"]))
            except (ValueError, KeyError, TypeError):
                logger.warning("Engagement mal forme sur la relance %s", relance.id)
                continue

            solde = soldes.get((relance.dossier_id, relance.debiteur_id), Decimal(0))
            if montant <= 0 or (solde > 0 and montant > solde):
                logger.warning("Montant promis incoherent sur la relance %s", relance.id)
                continue
            if echeance < relance.date_relance:
                logger.warning("Echeance promise anterieure a la relance %s", relance.id)
                continue

            engagements.append(
                EngagementExtrait(
                    relance_id=relance.id,
                    date_echeance_promesse=echeance,
                    montant_promis=montant,
                    extrait=str(entree.get("extrait", ""))[:1000],
                )
            )

        return engagements


_service = ExtractionPromessesIA()


def get_extraction_promesses_ia() -> ExtractionPromessesIA:
    return _service
