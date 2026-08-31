"""Normalisation des numeros de telephone, pour le dedoublonnage des debiteurs."""

import re

#: Longueur d'un numero national senegalais, indicatif retire.
LONGUEUR_NATIONALE = 9


def normaliser(valeur: str | None) -> str | None:
    """Forme canonique d'un numero, utilisee uniquement pour comparer.

    « +221 77 000 11 11 », « 00221770001111 » et « 770001111 » designent la meme
    ligne : sans cette normalisation, un fichier ou l'operateur a change de style
    en cours de route cree autant de fiches que d'ecritures.

    On ne garde que les chiffres, on retire le prefixe international puis, si le
    numero reste plus long qu'un numero national, on conserve les derniers
    chiffres — c'est la partie stable quel que soit l'indicatif.

    Limite assumee : deux numeros de pays differents partageant les memes 9
    derniers chiffres seraient confondus. Le contexte est senegalais, et le
    numero affiche reste celui saisi par l'utilisateur : seule la comparaison
    passe par ici.
    """
    if valeur is None:
        return None
    chiffres = re.sub(r"\D", "", valeur)
    if not chiffres:
        return None
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]
    if len(chiffres) > LONGUEUR_NATIONALE:
        chiffres = chiffres[-LONGUEUR_NATIONALE:]
    return chiffres or None
