from typing import Annotated

from fastapi import Depends

from app.ia.dossier import AnalyseDossierIA
from app.ia.service import RedactionService

#: Instance unique : le client HTTP sous-jacent est reutilise entre les requetes.
_service = RedactionService()


def get_redaction_service() -> RedactionService:
    return _service


RedactionServiceDep = Annotated[RedactionService, Depends(get_redaction_service)]

#: Meme raison : le client HTTP se reutilise d'une requete a l'autre.
_analyse_dossier = AnalyseDossierIA()


def get_analyse_dossier_ia() -> AnalyseDossierIA:
    return _analyse_dossier


AnalyseDossierIADep = Annotated[AnalyseDossierIA, Depends(get_analyse_dossier_ia)]
