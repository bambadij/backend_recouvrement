"""Service IA : analyse de dossiers, generation de messages de relance, priorisation.

A developper une fois le domaine metier (creances/paiements/relances) stabilise.
"""

from app.creances.models import Creance
from app.ia.llm import LLMClient, get_llm_client


class IAService:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm_client = llm_client or get_llm_client()

    async def analyser_dossier(self, creance: Creance) -> str:
        raise NotImplementedError

    async def generer_message_relance(self, creance: Creance, type_relance: str) -> str:
        raise NotImplementedError

    async def prioriser_creances(self, creances: list[Creance]) -> list[Creance]:
        raise NotImplementedError
