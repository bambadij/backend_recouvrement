"""Client LLM. Stub en attendant le choix du provider (Anthropic, OpenAI, local...)."""

from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def complete(self, prompt: str) -> str: ...


class NotImplementedLLMClient(LLMClient):
    async def complete(self, prompt: str) -> str:
        raise NotImplementedError("Le client LLM n'est pas encore configure")


def get_llm_client() -> LLMClient:
    return NotImplementedLLMClient()
