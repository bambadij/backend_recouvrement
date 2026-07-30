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


class OrganisationStats(BaseModel):
    #: None sur la vue plateforme, qui agrege toutes les organisations.
    organisation_id: int | None
    nb_clients: int
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
