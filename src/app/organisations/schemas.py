from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OrganisationBase(BaseModel):
    nom: str
    description: str | None = None


class OrganisationCreate(OrganisationBase):
    pass


class OrganisationUpdate(BaseModel):
    nom: str | None = None
    description: str | None = None
    is_active: bool | None = None


class OrganisationRead(OrganisationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TrancheBalanceAgee(BaseModel):
    """Une tranche d'ancienneté de la balance âgée.

    `tranche` reprend les identifiants attendus par le front : non-echu, 1-30,
    31-60, 61-90, 90+.
    """

    tranche: str
    montant: Decimal
    nb_creances: int


class Efficacite(BaseModel):
    """Indicateurs de vitesse de recouvrement, sur une période glissante.

    `dso` est une estimation : il rapporte l'encours au flux confié. `delai_moyen`
    est une mesure : il ne porte que sur des encaissements réels. Les deux peuvent
    diverger, et c'est justement l'écart qui est instructif.

    Les deux valent None quand leur base est vide — un zéro se lirait comme une
    performance parfaite alors qu'il signifie « rien à mesurer ».
    """

    periode_jours: int
    encours: Decimal
    flux_periode: Decimal
    dso: int | None
    delai_moyen: int | None
    #: Collection Effectiveness Index, en pourcentage. Part de ce qui *pouvait*
    #: etre encaisse sur la periode qui l'a effectivement ete. Contrairement au
    #: DSO, il neutralise l'effet du volume de creances nouvelles : un cabinet qui
    #: recoit deux fois plus de dossiers voit son DSO gonfler sans avoir moins
    #: bien travaille, son CEI non. None quand la base de calcul est vide.
    cei: int | None = None


class PointBalanceAgee(BaseModel):
    """La balance âgée à une date donnée, pour en suivre la déformation dans le temps."""

    date_ref: date
    tranches: dict[str, Decimal]


class MontantParMois(BaseModel):
    mois: str
    montant: Decimal


class LigneClassement(BaseModel):
    """Une ligne de classement : un libellé, un montant, un nombre d'éléments."""

    libelle: str
    montant: Decimal
    nombre: int


class ApercuOrganisation(BaseModel):
    """Une ligne de comparaison entre organisations, pour le SUPER_ADMIN.

    Aucun total n'est calcule sur l'ensemble : on compare, on n'additionne pas.
    Sommer les encours de cabinets distincts n'aurait pas de sens — donneurs d'ordre
    differents, et devises potentiellement differentes.

    `taux_recouvrement` et `part_plus_90j` valent None quand leur denominateur est nul :
    un 0 % se lirait comme un echec la ou il n'y a rien a mesurer.
    """

    organisation_id: int
    nom: str
    nb_utilisateurs: int
    nb_creances: int
    montant_restant: Decimal
    taux_recouvrement: int | None
    part_plus_90j: int | None


class SerieRecouvrement(BaseModel):
    """Les encaissements d'une organisation, mois par mois."""

    organisation_id: int
    nom: str
    #: Cle = mois au format YYYY-MM. Les mois sans encaissement sont a zero, pas absents,
    #: pour que le graphe ait des barres alignees sur un axe commun.
    montants: dict[str, Decimal]


class RecouvrementCompare(BaseModel):
    """Comparatif des encaissements entre organisations, sur une fenetre de mois.

    Deja mis en forme pour un graphe : un axe de mois commun, une serie par
    organisation. Le front n'a pas a pivoter les donnees.
    """

    mois: list[str]
    series: list[SerieRecouvrement]


class CaseRisque(BaseModel):
    """Une case de la cartographie : croisement d'un segment et d'un potentiel."""

    segment: str
    potentiel: str
    nb_creances: int
    montant: Decimal


class StatsPromesses(BaseModel):
    """Tenue des engagements de paiement obtenus des débiteurs.

    `taux_tenue` ne porte que sur les promesses déjà contrôlées : compter les
    ATTENDUE au dénominateur ferait chuter le taux à chaque nouvel engagement,
    alors qu'un engagement récent n'est pas un échec.
    """

    nb_attendues: int
    nb_tenues: int
    nb_partielles: int
    nb_rompues: int
    montant_attendu: Decimal
    taux_tenue: int | None


class PrevisionMois(BaseModel):
    """Encaissement prévu pour un mois, en séparant ses deux natures.

    `engage` vient de promesses datées et chiffrées : c'est du déclaratif du
    débiteur. `pondere` vient des échéances à venir, minorées par le potentiel de
    recouvrement issu de la segmentation. Les deux restent séparés parce qu'ils
    n'ont pas la même valeur probante.
    """

    mois: str
    engage: Decimal
    pondere: Decimal
    total: Decimal


class LigneProductivite(BaseModel):
    """Activité d'un agent. Les compteurs valent 0, jamais None : un agent sans
    relance a bien travaillé zéro dossier, ce n'est pas une mesure manquante."""

    agent: str
    relances_emises: int
    relances_avec_retour: int
    promesses_obtenues: int
    promesses_tenues: int
    nb_paiements: int
    montant_encaisse: Decimal


class Alerte(BaseModel):
    """Un signal calculé par règle déterministe, jamais par un modèle.

    Une alerte doit être vérifiable : l'agent qui la reçoit doit pouvoir
    retrouver le fait qui l'a déclenchée. `detail` porte ce fait.
    """

    code: str
    severite: str
    titre: str
    detail: str
    creance_id: int | None = None
    reference: str | None = None
    montant: Decimal | None = None


class Recommandation(BaseModel):
    """Une action a mener, rattachee au fait qui la motive.

    `fait_declencheur` n'est pas decoratif : c'est ce qui rend la recommandation
    verifiable. Sans lui, l'agent doit croire le modele sur parole.
    """

    titre: str
    action: str
    fait_declencheur: str
    urgence: str


class RecommandationsResponse(BaseModel):
    recommandations: list[Recommandation]
    modele: str


class JourActivite(BaseModel):
    """Ce qu'un agent a saisi un jour donne."""

    jour: date
    montant: Decimal
    nb_paiements: int


class MonActivite(BaseModel):
    """La semaine d'un agent, jour par jour.

    Sert la page « Mon espace » : un cumul sur trois mois ne dit pas si la
    semaine a ete active, il masque autant les journees pleines que les creuses.

    Comme partout ailleurs, `saisi_par_nom` dit qui a ENREGISTRE le versement,
    pas qui l'a obtenu — le libelle cote interface doit rester exact.
    """

    agent: str
    #: Un point par jour, du plus ancien au plus recent, jours vides compris.
    jours: list[JourActivite]
    total: Decimal


class OrganisationStats(BaseModel):
    #: None sur la vue plateforme, qui agrege toutes les organisations.
    organisation_id: int | None
    nb_debiteurs: int
    nb_creances: int
    creances_par_statut: dict[str, int]
    montant_total_initial: Decimal
    montant_total_restant: Decimal
    nb_paiements: int
    montant_total_encaisse: Decimal
    nb_relances: int
    nb_utilisateurs: int
    balance_agee: list[TrancheBalanceAgee]
    efficacite: Efficacite
    balance_agee_historique: list[PointBalanceAgee]
    echeances_a_venir: list[MontantParMois]
    top_debiteurs: list[LigneClassement]
    encaissements_par_utilisateur: list[LigneClassement]
    cartographie_risques: list[CaseRisque]
    promesses: StatsPromesses
    previsions: list[PrevisionMois]
    productivite: list[LigneProductivite]
    alertes: list[Alerte]


class ConsommationIA(BaseModel):
    """Ce qu'une fonction IA a consomme sur la fenetre demandee.

    Rendu aux administrateurs seuls : c'est une donnee de gestion, pas de
    travail. Un agent n'a pas a savoir combien coute le bouton qu'on lui
    demande d'utiliser — il finirait par ne plus l'utiliser.
    """

    fonction: str
    appels: int
    #: Comptes a part : un appel echoue apres avoir consomme des jetons se
    #: facture quand meme, et un pic d'echecs est ce qu'on veut voir.
    echecs: int
    jetons_entree: int
    jetons_sortie: int
    duree_moyenne_ms: int
