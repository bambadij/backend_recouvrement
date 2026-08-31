"""Ce que chaque appel de modele a consomme.

Six fonctions appellent le modele dans cette application, et jusqu'ici aucune
n'en laissait de trace : la facture arrivait indifferenciee, sans qu'on puisse
dire si elle venait du classement, des brouillons ou de l'assistant. Les
compteurs de jetons sont pourtant dans chaque reponse d'Anthropic — on ne les
lisait simplement pas.

Deux partis pris.

L'ecriture ne peut jamais faire echouer l'appel qu'elle observe. Un journal qui
casse la fonction journalisee est pire que pas de journal : `enregistrer` avale
ses propres erreurs et se contente de les tracer.

L'organisation et l'agent voyagent par variable de contexte plutot que par
parametre. Les six sites d'appel ont des signatures differentes et n'ont pour
la plupart aucune raison de connaitre l'utilisateur ; leur imposer un argument
de comptabilite melangerait la mesure au metier. La variable est posee une fois,
a l'authentification, et lue ici.
"""

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import true

from app.core.database import AsyncSessionLocal
from app.ia.models import AppelIA

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Appelant:
    """Qui a declenche l'appel. Nul hors requete authentifiee."""

    organisation_id: int | None
    agent_nom: str | None


#: Pose par get_current_user, lu par enregistrer. Un ContextVar et non une
#: variable de module : les requetes se chevauchent dans une boucle asyncio, et
#: une valeur partagee attribuerait les appels de l'un a l'autre.
appelant: ContextVar[Appelant | None] = ContextVar("appelant_ia", default=None)


class Chrono:
    """Mesure la duree d'un appel, meme quand il echoue.

    La duree d'un echec compte autant que celle d'un succes : c'est elle qui
    dit si le modele a repondu lentement ou si le reseau a lache tout de suite.
    """

    def __init__(self) -> None:
        self.debut = time.perf_counter()

    @property
    def millisecondes(self) -> int:
        return int((time.perf_counter() - self.debut) * 1000)


async def enregistrer(
    fonction: str,
    modele: str,
    chrono: Chrono,
    *,
    reponse=None,
    erreur: str | None = None,
) -> None:
    """Note un appel. N'echoue jamais vers l'appelant.

    `reponse` est l'objet rendu par le SDK : on y lit les jetons. Absent, c'est
    que l'appel a echoue, et seule la duree est retenue.
    """
    try:
        qui = appelant.get()
        usage = getattr(reponse, "usage", None)
        async with AsyncSessionLocal() as session:
            session.add(
                AppelIA(
                    fonction=fonction,
                    modele=getattr(reponse, "model", None) or modele,
                    organisation_id=qui.organisation_id if qui else None,
                    agent_nom=qui.agent_nom if qui else None,
                    jetons_entree=getattr(usage, "input_tokens", None),
                    jetons_sortie=getattr(usage, "output_tokens", None),
                    duree_ms=chrono.millisecondes,
                    erreur=erreur,
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — un journal ne casse pas ce qu'il observe
        logger.exception("Appel de modele non journalise (fonction=%s)", fonction)


@dataclass(frozen=True)
class ConsommationFonction:
    """Ce qu'une fonction a consomme sur la fenetre observee."""

    fonction: str
    appels: int
    echecs: int
    jetons_entree: int
    jetons_sortie: int
    duree_moyenne_ms: int


async def consommation(
    organisation_id: int | None, jours: int
) -> list[ConsommationFonction]:
    """La consommation par fonction, la plus lourde en tete.

    Lecture seule et hors du metier : aucune decision de l'application ne
    s'appuie dessus. Les echecs sont comptes a part — un appel qui a echoue
    apres avoir consomme des jetons se facture quand meme, et un pic d'echecs
    est justement ce qu'on veut voir.
    """
    from sqlalchemy import func, select  # local : ce module est importe tres tot

    borne = datetime.now(timezone.utc) - timedelta(days=jours)
    async with AsyncSessionLocal() as session:
        resultat = await session.execute(
            select(
                AppelIA.fonction,
                func.count().label("appels"),
                func.count().filter(AppelIA.erreur.isnot(None)).label("echecs"),
                func.coalesce(func.sum(AppelIA.jetons_entree), 0).label("entree"),
                func.coalesce(func.sum(AppelIA.jetons_sortie), 0).label("sortie"),
                func.coalesce(func.avg(AppelIA.duree_ms), 0).label("duree"),
            )
            .where(
                AppelIA.created_at >= borne,
                AppelIA.organisation_id == organisation_id
                if organisation_id is not None
                else true(),
            )
            .group_by(AppelIA.fonction)
            .order_by(func.sum(AppelIA.jetons_sortie).desc().nullslast())
        )
        return [
            ConsommationFonction(
                fonction=ligne.fonction,
                appels=ligne.appels,
                echecs=ligne.echecs,
                jetons_entree=int(ligne.entree),
                jetons_sortie=int(ligne.sortie),
                duree_moyenne_ms=int(ligne.duree),
            )
            for ligne in resultat.all()
        ]
