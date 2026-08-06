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
    debiteurs_crees: int
    debiteurs_reutilises: int
    creances_creees: int
    #: Encaissements anterieurs repris depuis la colonne « montant regle ».
    paiements_repris: int
    lignes_rejetees: list[ImportRowError]
