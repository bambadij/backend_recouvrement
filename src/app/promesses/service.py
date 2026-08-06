from datetime import date

from app.core.exceptions import ForbiddenException, NotFoundException
from app.creances.repository import CreanceRepository
from app.dossiers.service import DossierService
from app.ia.promesses import ExtractionPromessesIA
from app.paiements.repository import PaiementRepository
from app.promesses.models import Promesse, SourcePromesse, StatutPromesse
from app.promesses.repository import PromesseRepository
from app.promesses.schemas import (
    ControlePromessesResult,
    ExtractionPromessesResult,
    PromesseCreate,
    PromesseUpdate,
)
from app.relances.repository import RelanceRepository
from app.users.models import User


class PromesseService:
    def __init__(
        self,
        repository: PromesseRepository,
        paiement_repository: PaiementRepository,
        relance_repository: RelanceRepository,
        creance_repository: CreanceRepository,
        dossier_service: DossierService,
        extraction: ExtractionPromessesIA,
        current_user: User,
    ) -> None:
        self.repository = repository
        self.paiement_repository = paiement_repository
        self.relance_repository = relance_repository
        self.creance_repository = creance_repository
        self.dossier_service = dossier_service
        self.extraction = extraction
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException(
                "Un super-administrateur ne gere pas directement les donnees d'une organisation"
            )
        return self.current_user.organisation_id

    async def create_promesse(self, data: PromesseCreate) -> Promesse:
        organisation_id = self._writable_organisation_id()
        await self.dossier_service.get_dossier(data.dossier_id)  # 404 si dossier d'une autre organisation
        return await self.repository.create(data, organisation_id)

    async def get_promesse(self, promesse_id: int) -> Promesse:
        promesse = await self.repository.get_by_id(promesse_id)
        if promesse is None or (
            self.current_user.organisation_id is not None
            and promesse.organisation_id != self.current_user.organisation_id
        ):
            raise NotFoundException(f"Promesse {promesse_id} introuvable")
        return promesse

    async def list_promesses(
        self,
        skip: int = 0,
        limit: int = 100,
        dossier_id: int | None = None,
        statut: StatutPromesse | None = None,
    ) -> list[Promesse]:
        return await self.repository.list(
            skip=skip,
            limit=limit,
            dossier_id=dossier_id,
            organisation_id=self.current_user.organisation_id,
            statut=statut,
        )

    async def update_promesse(self, promesse_id: int, data: PromesseUpdate) -> Promesse:
        promesse = await self.get_promesse(promesse_id)
        self._writable_organisation_id()
        return await self.repository.update(promesse, data)

    async def delete_promesse(self, promesse_id: int) -> None:
        promesse = await self.get_promesse(promesse_id)
        self._writable_organisation_id()
        await self.repository.delete(promesse)

    async def controler_echues(self, jusqu_au: date | None = None) -> ControlePromessesResult:
        """Confronte les promesses echues aux encaissements reels.

        Entierement deterministe : aucun appel de modele. Une promesse est tenue si
        les paiements enregistres depuis le jour de l'engagement couvrent le montant
        promis, partielle s'il en est tombe une partie, rompue si rien n'est venu.
        La comparaison part de date_promesse et non de la date d'echeance : un
        debiteur qui paie en avance a tenu parole.

        Limite assumee : sur un debiteur portant plusieurs promesses chevauchantes,
        un meme encaissement peut en valider plusieurs. Les distinguer supposerait
        d'affecter chaque paiement a un engagement precis, information dont on ne
        dispose pas.
        """
        jusqu_au = jusqu_au or date.today()
        a_controler = await self.repository.list_a_controler(self.current_user.organisation_id, jusqu_au)

        tenues = partielles = rompues = 0
        for promesse in a_controler:
            encaisse = await self.paiement_repository.total_encaisse_depuis(
                promesse.dossier_id, promesse.debiteur_id, promesse.date_promesse
            )
            if encaisse >= promesse.montant_promis:
                promesse.statut = StatutPromesse.TENUE
                tenues += 1
            elif encaisse > 0:
                promesse.statut = StatutPromesse.PARTIELLE
                partielles += 1
            else:
                promesse.statut = StatutPromesse.ROMPUE
                rompues += 1

        if a_controler:
            await self.repository.commit()

        return ControlePromessesResult(
            promesses_controlees=len(a_controler),
            tenues=tenues,
            partielles=partielles,
            rompues=rompues,
        )

    async def extraire_depuis_relances(self, limite: int = 200) -> ExtractionPromessesResult:
        """Relit les comptes rendus de relance et en tire les engagements datables.

        Idempotent : une relance ayant deja produit une promesse est ignoree, donc
        rejouer la passe ne duplique pas les engagements deja extraits.
        """
        organisation_id = self._writable_organisation_id()

        relances = await self.relance_repository.list(
            limit=limite, organisation_id=organisation_id, avec_resultat=True
        )
        deja_traitees = await self.repository.list_relance_ids_deja_traites(organisation_id)
        a_analyser = [r for r in relances if r.id not in deja_traitees]

        if not a_analyser:
            return ExtractionPromessesResult(
                relances_analysees=0, promesses_creees=0, sans_engagement=0, modele=""
            )

        soldes = await self.creance_repository.soldes_par_dossier_debiteur(
            [(r.dossier_id, r.debiteur_id) for r in a_analyser]
        )
        engagements, modele = await self.extraction.extraire(a_analyser, soldes)

        relances_par_id = {r.id: r for r in a_analyser}
        promesses = [
            Promesse(
                organisation_id=organisation_id,
                dossier_id=relances_par_id[e.relance_id].dossier_id,
                debiteur_id=relances_par_id[e.relance_id].debiteur_id,
                relance_id=e.relance_id,
                date_promesse=relances_par_id[e.relance_id].date_relance,
                date_echeance_promesse=e.date_echeance_promesse,
                montant_promis=e.montant_promis,
                source=SourcePromesse.INFEREE,
                commentaire=e.extrait,
            )
            for e in engagements
        ]
        await self.repository.create_many(promesses)

        return ExtractionPromessesResult(
            relances_analysees=len(a_analyser),
            promesses_creees=len(promesses),
            sans_engagement=len(a_analyser) - len(promesses),
            modele=modele,
        )
