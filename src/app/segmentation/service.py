from collections import Counter

from app.core.exceptions import ForbiddenException, NotFoundException
from app.ia.segmentation import ClassificationIA
from app.segmentation.models import PotentielRecouvrement, Segmentation
from app.segmentation.repository import SegmentationRepository
from app.segmentation.schemas import (
    DossierSegmente,
    SegmentationRead,
    SegmentationRequest,
    SegmentationRunResult,
)
from app.users.models import User

#: Ordre de traitement : d'abord ce qui a le plus de chances d'aboutir. A
#: potentiel egal, le montant restant tranche. C'est ce tri, et non le risque,
#: qui repond a « travailler en priorite sur les dossiers les plus rentables » :
#: un dossier critique est souvent celui ou l'effort rapporte le moins.
_RANG_POTENTIEL = {
    PotentielRecouvrement.FORT: 0,
    PotentielRecouvrement.MOYEN: 1,
    PotentielRecouvrement.FAIBLE: 2,
}


class SegmentationService:
    def __init__(
        self,
        repository: SegmentationRepository,
        classification: ClassificationIA,
        current_user: User,
    ) -> None:
        self.repository = repository
        self.classification = classification
        self.current_user = current_user

    def _writable_organisation_id(self) -> int:
        if self.current_user.organisation_id is None:
            raise ForbiddenException(
                "Un super-administrateur ne segmente pas le portefeuille d'une organisation"
            )
        return self.current_user.organisation_id

    async def lancer(self, demande: SegmentationRequest) -> SegmentationRunResult:
        """Calcule les faits, fait classer les dossiers, enregistre le resultat."""
        organisation_id = self._writable_organisation_id()

        faits = await self.repository.charger_faits(
            organisation_id, limite=demande.limite, inclure_deja_classes=demande.forcer
        )
        if not faits:
            return SegmentationRunResult(
                dossiers_analyses=0,
                dossiers_classes=0,
                ignores=0,
                repartition={},
                modele="",
            )

        classements, modele = await self.classification.classer(faits)
        faits_par_id = {f.creance_id: f for f in faits}

        segmentations = [
            Segmentation(
                organisation_id=organisation_id,
                creance_id=c.creance_id,
                segment=c.segment,
                potentiel=c.potentiel,
                justification=c.justification,
                anciennete_jours=faits_par_id[c.creance_id].anciennete_jours,
                taux_regle=faits_par_id[c.creance_id].taux_regle,
                nb_relances=faits_par_id[c.creance_id].nb_relances,
                nb_promesses_rompues=faits_par_id[c.creance_id].nb_promesses_rompues,
                modele=modele,
            )
            for c in classements
        ]
        await self.repository.enregistrer(segmentations)

        repartition = Counter(s.segment.value for s in segmentations)
        return SegmentationRunResult(
            dossiers_analyses=len(faits),
            dossiers_classes=len(segmentations),
            # Ce que le modele n'a pas rendu : trace plutot que silence.
            ignores=len(faits) - len(segmentations),
            repartition=dict(repartition),
            modele=modele,
        )

    async def segmentation_de_creance(self, creance_id: int) -> SegmentationRead:
        """Le classement courant d'une creance, pour l'afficher sur son detail.

        Lecture pure : aucun appel de modele. Une creance jamais classee — parce
        qu'elle est recente, ou soldee et donc hors de la file — n'est pas une
        erreur applicative, mais l'interface doit pouvoir le distinguer d'un
        classement existant : d'ou le 404 plutot qu'un objet vide.
        """
        segmentation = await self.repository.get_scoped_by_creance(
            creance_id, self.current_user.organisation_id
        )
        if segmentation is None:
            raise NotFoundException("Cette creance n'a pas encore ete classee")
        return SegmentationRead.model_validate(segmentation)

    async def file_de_travail(self, limit: int = 200) -> list[DossierSegmente]:
        """Les dossiers classes, dans l'ordre ou les agents doivent les traiter."""
        lignes = await self.repository.list_dossiers_segmentes(
            self.current_user.organisation_id, limit=limit
        )

        dossiers = [
            DossierSegmente(
                creance_id=creance.id,
                reference=creance.reference,
                debiteur=f"{debiteur.prenom} {debiteur.nom}".strip(),
                etablissement=creance.etablissement,
                cycle=creance.cycle,
                financeur=creance.financeur,
                montant_restant=creance.montant_restant,
                date_echeance=creance.date_echeance,
                anciennete_jours=segmentation.anciennete_jours,
                segment=segmentation.segment,
                potentiel=segmentation.potentiel,
                justification=segmentation.justification,
                rang=0,
                calcule_le=segmentation.calcule_le,
            )
            for segmentation, creance, debiteur in lignes
        ]

        dossiers.sort(key=lambda d: (_RANG_POTENTIEL[d.potentiel], -d.montant_restant))
        for rang, dossier in enumerate(dossiers, start=1):
            dossier.rang = rang
        return dossiers
