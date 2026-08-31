"""Quel canal tenter, et pourquoi.

Calcule ici et pas par le modele, pour la meme raison que partout ailleurs :
c'est une regle, elle doit etre rejouable et explicable. L'agent voit la raison
en toutes lettres et peut la contredire d'un clic ; un modele qui « sentirait »
qu'il faut appeler ne se contredirait jamais deux fois pareil.

Ce n'est PAS un apprentissage. Rien dans la base ne permet aujourd'hui de dire
quel canal fait payer : les issues viennent d'etre ouvertes a la saisie, et il
faudra des mois de retours consignes avant qu'un taux par canal veuille dire
quelque chose. En attendant, deux regles simples et honnetes : on retourne la
ou le debiteur a deja repondu, sinon on monte d'un cran.
"""

from app.relances.models import TypeRelance

#: L'echelle, du plus leger au plus lourd. Elle dit l'ordre d'escalade et rien
#: d'autre : un email coute moins cher qu'un appel, qui coute moins cher qu'une
#: mise en demeure — en argent, en temps, et en relation avec le client.
ECHELLE: list[TypeRelance] = [
    TypeRelance.EMAIL,
    TypeRelance.SMS,
    TypeRelance.WHATSAPP,
    TypeRelance.APPEL,
    TypeRelance.MISE_EN_DEMEURE,
]

#: Dernier cran que la regle propose d'elle-meme.
#:
#: La mise en demeure est un acte juridique : sa valeur tient a la forme et a
#: l'accuse de reception, et l'engager doit rester une decision prise par un
#: humain qui sait ce qu'il declenche. La regle s'arrete donc a l'appel et le
#: dit, plutot que de la proposer comme un cran de plus.
DERNIER_CRAN_AUTOMATIQUE = TypeRelance.APPEL

_LIBELLES = {
    TypeRelance.EMAIL: "email",
    TypeRelance.SMS: "SMS",
    TypeRelance.WHATSAPP: "WhatsApp",
    TypeRelance.APPEL: "appel",
    TypeRelance.MISE_EN_DEMEURE: "mise en demeure",
}


def canal_conseille(canaux: list) -> tuple[TypeRelance, str]:
    """Le canal a tenter, et la phrase qui le justifie.

    `canaux` porte, par canal, le nombre d'envois et le nombre de retours
    obtenus — la forme de CanalDebiteur. La phrase rendue est destinee a etre
    affichee telle quelle : elle explique la regle, elle ne la commente pas.
    """
    tentes = {c.canal: c for c in canaux if c.envoyees > 0}

    if not tentes:
        return TypeRelance.EMAIL, "Aucune relance encore tentee : on commence par le plus leger."

    # 1. Un canal qui a deja fait reagir ce debiteur. C'est le seul signal
    #    reellement observe, et il prime sur toute escalade : inutile de monter
    #    d'un cran quand on sait ou il decroche.
    repondus = [c for c in tentes.values() if c.avec_reponse > 0]
    if repondus:
        meilleur = max(repondus, key=lambda c: (c.avec_reponse, -c.envoyees))
        canal = TypeRelance(meilleur.canal)
        return canal, f"Il a deja repondu par {_LIBELLES[canal]} ({meilleur.avec_reponse} fois)."

    # 2. Sinon on monte d'un cran depuis le plus lourd deja tente. Repeter le
    #    meme canal reste sans reponse serait refaire ce qui n'a pas marche.
    plus_lourd = max(
        (TypeRelance(c) for c in tentes),
        key=lambda t: ECHELLE.index(t) if t in ECHELLE else -1,
    )
    rang = ECHELLE.index(plus_lourd)

    if plus_lourd is DERNIER_CRAN_AUTOMATIQUE or rang >= ECHELLE.index(DERNIER_CRAN_AUTOMATIQUE):
        return (
            DERNIER_CRAN_AUTOMATIQUE,
            "Tous les canaux amiables ont ete tentes sans reponse. "
            "La suite serait une mise en demeure — c'est un acte juridique, a decider vous-meme.",
        )

    suivant = ECHELLE[rang + 1]
    envoyees = tentes[plus_lourd.value].envoyees
    fois = "1 fois" if envoyees == 1 else f"{envoyees} fois"
    # Premiere lettre seulement : capitalize() abaisse le reste et rendait
    # « Sms » et « Whatsapp », qui ne s'ecrivent pas ainsi.
    libelle = _LIBELLES[plus_lourd]
    return (
        suivant,
        f"{libelle[0].upper()}{libelle[1:]} tente {fois} sans reponse : on monte d'un cran.",
    )
