from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.relances.models import IssueRelance, StatutRelance, TypeRelance
from app.segmentation.models import PotentielRecouvrement, SegmentRisque


class RelanceBase(BaseModel):
    dossier_id: int
    #: Le debiteur vise dans ce dossier : un dossier peut en compter trente.
    debiteur_id: int
    type_relance: TypeRelance
    date_relance: date = Field(default_factory=date.today)
    contenu: str | None = None


class RelanceCreate(RelanceBase):
    #: PLANIFIEE par defaut : on prepare une relance avant de l'emettre.
    #:
    #: La file de travail, elle, enregistre APRES coup — l'agent vient
    #: d'envoyer depuis son propre outil et le declare. Lui imposer de creer
    #: puis de modifier ferait deux ecritures pour un seul geste.
    statut: StatutRelance = StatutRelance.PLANIFIEE


class RelanceUpdate(BaseModel):
    statut: StatutRelance | None = None
    issue: IssueRelance | None = None
    resultat: str | None = None


class IssueRelanceRequest(BaseModel):
    """Le retour obtenu, tel que l'agent le consigne en raccrochant.

    Le montant et l'echeance ne sont demandes que pour A_PROMIS, et ils vont
    alors droit dans une promesse : un engagement est une donnee structuree, et
    la faire ecrire en toutes lettres pour la faire relire ensuite par un modele
    coute un appel et une chance de se tromper. L'agent qui vient de raccrocher
    a le montant et la date en tete.
    """

    issue: IssueRelance
    #: La nuance, facultative quelle que soit l'issue.
    resultat: str | None = Field(default=None, max_length=1000)
    montant_promis: Decimal | None = Field(default=None, gt=0)
    date_echeance_promesse: date | None = None

    @model_validator(mode="after")
    def _coherence(self) -> "IssueRelanceRequest":
        engage = self.montant_promis is not None or self.date_echeance_promesse is not None
        if engage and self.issue is not IssueRelance.A_PROMIS:
            raise ValueError(
                "Un montant ou une echeance ne se joint qu'a l'issue « a promis de payer »"
            )
        # Les deux ou aucun : une promesse sans date ne se suit pas, un montant
        # sans date ne s'echoit jamais, et l'inverse ne se rapproche d'aucun
        # paiement. A_PROMIS sans les deux reste permis — l'agent note l'issue
        # maintenant et complete l'engagement plus tard.
        if (self.montant_promis is None) != (self.date_echeance_promesse is None):
            raise ValueError("Le montant promis et son echeance vont ensemble")
        return self


class FileDisponible(BaseModel):
    """Un critere de travail, avec le nombre de debiteurs qu'il retient."""

    cle: str
    libelle: str
    effectif: int


class LigneARelancer(BaseModel):
    """Un debiteur a relancer dans un dossier, toutes ses factures echues confondues.

    L'unite n'est pas la facture : une relance vise un debiteur A L'INTERIEUR
    d'un dossier, et un seul courrier couvre tous ses impayes. Presenter la file
    facture par facture ferait envoyer trois messages a quelqu'un qui doit trois
    factures.
    """

    dossier_id: int
    dossier_reference: str | None
    debiteur_id: int
    debiteur_nom: str
    #: Expose a part : les reprises de stock recopient souvent la raison sociale
    #: dans le nom, et l'interface doit pouvoir eviter de l'afficher deux fois.
    debiteur_entreprise: str | None

    nb_factures: int
    montant_restant: Decimal
    #: Retard de la facture la plus ancienne : c'est l'anciennete de la dette.
    jours_retard: int
    #: La plus ancienne facture echue, point d'entree vers la page de detail.
    creance_id: int
    #: Sa reference : c'est elle, et non l'identifiant, que porte l'URL du detail.
    creance_reference: str

    #: Derniere relance PARTIE. Une relance planifiee n'a rien emis : la compter
    #: reviendrait a dire qu'on a relance quelqu'un qui n'a rien recu.
    derniere_relance: date | None
    derniere_relance_canal: TypeRelance | None
    #: Vrai si cette derniere relance a etabli un contact — promesse, reponse ou
    #: refus. Faux quand elle est restee sans reponse ET quand elle n'a pas
    #: encore ete annotee : c'est « derniere_relance_issue » qui distingue les deux.
    derniere_relance_repondue: bool
    #: Identifiant de cette derniere relance partie : c'est elle qu'on annote
    #: depuis la file, sans passer par la fiche creance.
    derniere_relance_id: int | None = None
    #: Son issue, ou None tant que personne ne l'a consignee.
    derniere_relance_issue: IssueRelance | None = None
    #: La nuance saisie avec l'issue, affichee telle quelle sous la ligne.
    derniere_relance_resultat: str | None = None

    #: Relance deja planifiee et non emise, s'il y en a une. Sans ce temoin, la
    #: file afficherait « jamais relance » a cote d'une relance en attente et
    #: l'agent en creerait une seconde.
    relance_planifiee_id: int | None

    # --- Classement, quand il a ete calcule ---------------------------------
    #
    # Nuls tant qu'aucune passe de segmentation n'a tourne. La file reste alors
    # exactement celle d'avant : ces champs ajoutent un ordre et une explication,
    # ils ne conditionnent rien.
    segment: SegmentRisque | None = None
    potentiel: PotentielRecouvrement | None = None
    #: Pourquoi ce rang, dans les mots du modele. Porte sur la creance elue.
    justification: str | None = None
    #: La creance qui a decide du rang du debiteur — pire segment, puis plus gros
    #: montant. C'est d'elle que parle la justification.
    creance_classee_reference: str | None = None


class FileDeTravail(BaseModel):
    """La file du jour : les criteres disponibles, et les lignes de l'un d'eux."""

    file_active: str
    files: list[FileDisponible]
    lignes: list[LigneARelancer]

    #: « classement » ou « montant ». Le classement quand il existe, sinon le
    #: montant — l'ecran ne depend jamais d'une passe de modele.
    tri_actif: str
    #: Quand la derniere passe a tourne. Nul si aucune. Rendu a tous les roles :
    #: un agent ne declenche pas le classement mais doit savoir s'il est frais.
    classement_calcule_le: datetime | None = None
    #: Lignes classees dans CE critere. Zero signifie qu'un tri par classement
    #: n'y changerait rien, meme si le portefeuille en compte ailleurs.
    classees: int = 0
    #: Lignes de cette file qui n'ont pas encore ete classees.
    non_classees: int = 0


class RelanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organisation_id: int
    dossier_id: int
    debiteur_id: int
    type_relance: TypeRelance
    date_relance: date
    statut: StatutRelance
    contenu: str | None
    issue: IssueRelance | None
    resultat: str | None
    cree_par_nom: str | None
    created_at: datetime
