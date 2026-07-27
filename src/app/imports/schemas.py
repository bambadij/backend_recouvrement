from pydantic import BaseModel


class ImportRowError(BaseModel):
    ligne: int
    message: str


class ImportPreview(BaseModel):
    total_lignes: int
    lignes_valides: int
    lignes_invalides: int
    erreurs: list[ImportRowError]


class ImportResult(BaseModel):
    clients_crees: int
    clients_reutilises: int
    creances_creees: int
    lignes_rejetees: list[ImportRowError]
