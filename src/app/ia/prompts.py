"""Templates de prompts pour la partie IA (analyse de dossiers, relances, priorisation)."""

ANALYSE_DOSSIER_PROMPT = """
Tu es un assistant specialise en recouvrement de creances.
Analyse le dossier suivant et donne une evaluation du risque de non-paiement.

Client : {client}
Creance : {creance}
Historique de paiements : {paiements}
Historique de relances : {relances}
"""

GENERATION_RELANCE_PROMPT = """
Redige un message de relance {type_relance} pour le client suivant, sur un ton {ton}.

Client : {client}
Creance : {creance}
Montant restant du : {montant_restant}
Nombre de relances precedentes : {nombre_relances}
"""

PRIORISATION_PROMPT = """
Classe les creances suivantes par ordre de priorite de recouvrement,
en tenant compte du montant, de l'anciennete et de l'historique de paiement.

Creances : {creances}
"""
