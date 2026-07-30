from typing import Annotated

from fastapi import Depends

from app.ia.service import RedactionService

#: Instance unique : le client HTTP sous-jacent est reutilise entre les requetes.
_service = RedactionService()


def get_redaction_service() -> RedactionService:
    return _service


RedactionServiceDep = Annotated[RedactionService, Depends(get_redaction_service)]
