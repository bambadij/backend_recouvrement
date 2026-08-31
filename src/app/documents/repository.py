from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import undefer

from app.documents.models import Document


class DocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, document: Document) -> Document:
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def get_by_id(self, document_id: int) -> Document | None:
        """Sans le contenu : la verification d'acces n'a pas besoin des octets."""
        return await self.db.get(Document, document_id)

    async def get_avec_contenu(self, document_id: int) -> Document | None:
        """Avec les octets, pour le seul cas qui les demande : le telechargement."""
        result = await self.db.execute(
            select(Document).where(Document.id == document_id).options(undefer(Document.contenu))
        )
        return result.scalar_one_or_none()

    async def list_pour(
        self,
        organisation_id: int | None,
        dossier_id: int | None = None,
        creance_id: int | None = None,
        paiement_id: int | None = None,
    ) -> list[Document]:
        query = select(Document)
        if organisation_id is not None:
            query = query.where(Document.organisation_id == organisation_id)
        if dossier_id is not None:
            query = query.where(Document.dossier_id == dossier_id)
        if creance_id is not None:
            query = query.where(Document.creance_id == creance_id)
        if paiement_id is not None:
            query = query.where(Document.paiement_id == paiement_id)

        result = await self.db.execute(query.order_by(Document.created_at.desc()))
        return list(result.scalars().all())

    async def delete(self, document: Document) -> None:
        await self.db.delete(document)
        await self.db.commit()
