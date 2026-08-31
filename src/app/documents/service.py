from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.creances.service import CreanceService
from app.documents.models import Document
from app.documents.repository import DocumentRepository
from app.documents.schemas import TAILLE_MAX, TYPES_AUTORISES
from app.dossiers.service import DossierService
from app.paiements.repository import PaiementRepository
from app.users.models import User


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        dossier_service: DossierService,
        creance_service: CreanceService,
        paiement_repository: PaiementRepository,
        current_user: User,
    ) -> None:
        self.repository = repository
        self.dossier_service = dossier_service
        self.creance_service = creance_service
        self.paiement_repository = paiement_repository
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException(
                "Un super-administrateur ne gere pas directement les donnees d'une organisation"
            )
        return self.current_user.organisation_id

    async def _verifier_cible(
        self, dossier_id: int | None, creance_id: int | None, paiement_id: int | None
    ) -> None:
        """Une piece se rattache a un objet, et a un seul.

        L'acces est verifie sur la CIBLE, pas sur la piece : c'est le dossier ou
        la facture qui dit a quelle organisation elle appartient. Sans ce
        controle, il suffirait d'inventer un identifiant pour deposer une piece
        dans le dossier d'un autre cabinet.
        """
        cibles = [dossier_id, creance_id, paiement_id]
        if sum(1 for c in cibles if c is not None) != 1:
            raise BadRequestException(
                "Une piece se rattache a un dossier, une facture ou un paiement — a un seul."
            )

        if dossier_id is not None:
            await self.dossier_service.get_dossier(dossier_id)
        elif creance_id is not None:
            await self.creance_service.get_creance(creance_id)
        else:
            paiement = await self.paiement_repository.get_by_id(paiement_id)  # type: ignore[arg-type]
            if paiement is None:
                raise NotFoundException(f"Paiement {paiement_id} introuvable")
            # Le paiement ne porte pas d'organisation : c'est sa creance qui la
            # porte, et get_creance refuse celles des autres organisations.
            await self.creance_service.get_creance(paiement.creance_id)

    async def deposer(
        self,
        nom: str,
        type_mime: str,
        contenu: bytes,
        dossier_id: int | None = None,
        creance_id: int | None = None,
        paiement_id: int | None = None,
    ) -> Document:
        organisation_id = self._writable_organisation_id()
        await self._verifier_cible(dossier_id, creance_id, paiement_id)

        if not contenu:
            raise BadRequestException("Le fichier est vide.")
        if len(contenu) > TAILLE_MAX:
            raise BadRequestException(
                f"Le fichier depasse {TAILLE_MAX // (1024 * 1024)} Mo. "
                "Reduisez la resolution du scan ou envoyez-le en plusieurs pieces."
            )
        # Liste blanche : une liste d'interdits laisse toujours passer ce qu'on
        # n'avait pas prevu. Le type vient du navigateur, il n'est donc pas une
        # preuve — c'est un premier filtre, pas une garantie.
        if type_mime not in TYPES_AUTORISES:
            raise BadRequestException(
                "Type de fichier refuse. Sont acceptes : PDF, images, Word et Excel."
            )

        document = Document(
            organisation_id=organisation_id,
            dossier_id=dossier_id,
            creance_id=creance_id,
            paiement_id=paiement_id,
            # Le nom d'origine ne sert qu'a l'affichage et au telechargement. Il
            # ne construit aucun chemin : rien ici ne touche au systeme de
            # fichiers, le contenu part en base.
            nom=nom[:255],
            type_mime=type_mime,
            taille=len(contenu),
            contenu=contenu,
            depose_par_nom=f"{self.current_user.prenom} {self.current_user.nom}".strip() or None,
        )
        return await self.repository.create(document)

    async def lister(
        self,
        dossier_id: int | None = None,
        creance_id: int | None = None,
        paiement_id: int | None = None,
    ) -> list[Document]:
        if dossier_id is None and creance_id is None and paiement_id is None:
            raise BadRequestException(
                "Precisez de quoi vous voulez les pieces : dossier, facture ou paiement."
            )
        await self._verifier_cible(dossier_id, creance_id, paiement_id)
        return await self.repository.list_pour(
            self.current_user.organisation_id,
            dossier_id=dossier_id,
            creance_id=creance_id,
            paiement_id=paiement_id,
        )

    async def telecharger(self, document_id: int) -> Document:
        """La piece avec ses octets, apres verification de l'organisation.

        C'est le seul endroit qui charge le binaire. Le controle se fait ici et
        non par une URL secrete : un lien devinable donnerait les pieces d'un
        autre cabinet.
        """
        document = await self.repository.get_avec_contenu(document_id)
        if document is None or (
            self.current_user.organisation_id is not None
            and document.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Document {document_id} introuvable")
        return document

    async def supprimer(self, document_id: int) -> None:
        document = await self.repository.get_by_id(document_id)
        if document is None or (
            self.current_user.organisation_id is not None
            and document.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Document {document_id} introuvable")
        self._writable_organisation_id()
        await self.repository.delete(document)
