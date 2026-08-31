import io

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import StreamingResponse

from app.imports.dependencies import ImportServiceDep
from app.imports.schemas import ImportPreview, ImportResult
from app.imports.service import ImportService

router = APIRouter(prefix="/imports", tags=["imports"])

XLSX_MEDIA = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/creances/preview", response_model=ImportPreview)
async def preview_import_creances(service: ImportServiceDep, file: UploadFile = File(...)) -> ImportPreview:
    content = await file.read()
    return await service.preview(file.filename or "", content)


@router.post("/creances", response_model=ImportResult, status_code=status.HTTP_201_CREATED)
async def import_creances(
    service: ImportServiceDep,
    dossier_id: int = Form(..., description="Le dossier que ce fichier alimente"),
    file: UploadFile = File(...),
) -> ImportResult:
    content = await file.read()
    return await service.commit(file.filename or "", content, dossier_id)


@router.get("/creances/modele")
async def download_modele() -> StreamingResponse:
    data = ImportService.build_template()
    return StreamingResponse(
        io.BytesIO(data),
        media_type=XLSX_MEDIA,
        headers={"Content-Disposition": "attachment; filename=modele_import_creances.xlsx"},
    )
