from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, Response, UploadFile, status

from app.documents.dependencies import DocumentServiceDep
from app.documents.schemas import DocumentRead

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def deposer_document(
    service: DocumentServiceDep,
    file: UploadFile = File(...),
    dossier_id: int | None = Form(None),
    creance_id: int | None = Form(None),
    paiement_id: int | None = Form(None),
) -> DocumentRead:
    """Depose une piece sur un dossier, une facture ou un paiement.

    Le contenu part en base : pas de repertoire a monter, pas de fichier
    orphelin apres une suppression, et une sauvegarde qui ramene la piece et la
    ligne qu'elle justifie dans le meme etat.
    """
    contenu = await file.read()
    document = await service.deposer(
        nom=file.filename or "piece",
        type_mime=file.content_type or "application/octet-stream",
        contenu=contenu,
        dossier_id=dossier_id,
        creance_id=creance_id,
        paiement_id=paiement_id,
    )
    return DocumentRead.model_validate(document)


@router.get("", response_model=list[DocumentRead])
async def lister_documents(
    service: DocumentServiceDep,
    dossier_id: int | None = Query(None),
    creance_id: int | None = Query(None),
    paiement_id: int | None = Query(None),
) -> list[DocumentRead]:
    """Les pieces d'un objet, sans leur contenu."""
    documents = await service.lister(
        dossier_id=dossier_id, creance_id=creance_id, paiement_id=paiement_id
    )
    return [DocumentRead.model_validate(d) for d in documents]


@router.get("/{document_id}/contenu")
async def telecharger_document(document_id: int, service: DocumentServiceDep) -> Response:
    """Sert le fichier apres verification de l'organisation.

    Jamais un repertoire statique : une URL devinable donnerait acces aux pieces
    d'un autre cabinet, et toute la cloison multi-tenant tomberait avec elle.

    « attachment » et non « inline » : un PDF ou une image ouverts dans l'onglet
    s'executeraient dans l'origine de l'application. Le fichier vient d'un tiers,
    il se telecharge.
    """
    document = await service.telecharger(document_id)

    # RFC 5987 : un nom accentue ou avec des espaces casse l'en-tete simple.
    nom = quote(document.nom)
    return Response(
        content=document.contenu,
        media_type=document.type_mime,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{nom}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def supprimer_document(document_id: int, service: DocumentServiceDep) -> None:
    await service.supprimer(document_id)
