from datetime import datetime

from pydantic import BaseModel, ConfigDict

#: 5 Mo. Le contenu vit en base : chaque piece pese sur les sauvegardes et sur
#: la restauration. Un scan de facture tient largement dessous ; une video ou un
#: PDF de mille pages n'a rien a faire dans un dossier de recouvrement.
TAILLE_MAX = 5 * 1024 * 1024

#: Ce qu'un dossier de recouvrement contient legitimement : des pieces qu'on
#: montre a un debiteur ou a un juge. Liste blanche, et non liste noire : une
#: liste d'interdits laisse toujours passer ce qu'on n'avait pas prevu.
TYPES_AUTORISES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class DocumentRead(BaseModel):
    """Une piece, sans son contenu.

    Les octets ne voyagent que sur le telechargement : les inclure ici ferait
    transiter des megaoctets a chaque affichage de liste.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    dossier_id: int | None
    creance_id: int | None
    paiement_id: int | None
    nom: str
    type_mime: str
    taille: int
    depose_par_nom: str | None
    created_at: datetime
