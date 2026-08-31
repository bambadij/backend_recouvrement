"""Un plan de reglement en mensualites egales.

Calcule ici, jamais par le modele. Une division se trompe une fois sur mille
chez un humain et jamais chez Python ; un modele de langage, lui, se trompera un
jour sur l'arrondi de la derniere mensualite — et ce sera dans un courrier
deja parti chez un client. Le modele habille le plan, il ne le calcule pas.

Meme regle que le simulateur de la fiche facture : le 5 de chaque mois, a
partir du mois suivant. Deux calculs differents pour la meme proposition
finiraient par afficher deux plans distincts sur le meme dossier.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

#: Jour du mois retenu pour chaque echeance. Le 5 laisse passer les paies de
#: fin de mois, qui sont la source de tresorerie la plus courante ici.
JOUR_ECHEANCE = 5


@dataclass(frozen=True)
class Echeance:
    numero: int
    date_echeance: date
    montant: Decimal


def generer(restant: Decimal, mensualites: int, aujourdhui: date | None = None) -> list[Echeance]:
    """Decoupe `restant` en `mensualites` echeances, la derniere absorbant l'arrondi.

    Renvoie une liste vide quand il n'y a rien a echelonner : proposer un plan
    sur zero franc n'a pas de sens, et laisser le modele improviser sur une
    liste vide en produirait un quand meme.
    """
    if restant <= 0 or mensualites <= 0:
        return []

    # Tout se calcule en francs entiers. Le FCFA n'a pas de subdivision, et la
    # colonne en porte deux decimales par commodite de schema : les garder
    # faisait sortir « 1 152 181,00 » a cote de « 1 152 182 » dans le meme
    # courrier. Le total ainsi arrondi peut s'ecarter du solde de moins d'un
    # franc — ce que personne ne reclamera, contrairement a un plan dont les
    # lignes n'ont pas la meme forme.
    total = restant.quantize(Decimal("1"))
    base = (total / mensualites).quantize(Decimal("1"))
    plan: list[Echeance] = []
    for i in range(mensualites):
        mois = aujourdhui or date.today()
        annee = mois.year + (mois.month + i) // 12
        numero_mois = (mois.month + i) % 12 + 1
        # La derniere reprend le reste exact : sans cela la somme des mensualites
        # ne retombe pas sur le solde, et le debiteur reste devoir trois francs.
        montant = total - base * (mensualites - 1) if i == mensualites - 1 else base
        plan.append(
            Echeance(
                numero=i + 1,
                date_echeance=date(annee, numero_mois, JOUR_ECHEANCE),
                montant=montant,
            )
        )
    return plan
