-- Ce que chaque appel de modele a consomme.
--
-- Six fonctions appellent le modele et aucune n'en laissait de trace : la
-- facture arrivait indifferenciee, sans qu'on puisse dire si elle venait du
-- classement, des brouillons de relance ou de l'assistant. Les compteurs de
-- jetons sont pourtant dans chaque reponse d'Anthropic — on ne les lisait pas.
--
-- Cette table sert a MESURER, pas a decider. Rien dans l'application ne doit
-- se mettre a en dependre : un quota qui bloquerait une relance parce qu'une
-- ligne de journal manque ferait echouer le travail pour une raison comptable.

CREATE TABLE IF NOT EXISTS appels_ia (
    id              SERIAL PRIMARY KEY,

    -- Une chaine et non un enum : de nouvelles fonctions apparaitront, et une
    -- migration d'enum pour chacune freinerait ce qu'on cherche a observer.
    fonction        VARCHAR(60) NOT NULL,
    modele          VARCHAR(80) NOT NULL,

    -- SET NULL et non CASCADE : la consommation passee reste vraie meme si
    -- l'organisation disparait, et c'est precisement ce qu'on veut facturer.
    organisation_id INTEGER REFERENCES organisations(id) ON DELETE SET NULL,
    -- Instantane du nom, comme paiements.saisi_par_nom.
    agent_nom       VARCHAR(200),

    -- Nuls quand l'appel a echoue avant d'obtenir une reponse.
    jetons_entree   INTEGER,
    jetons_sortie   INTEGER,
    duree_ms        INTEGER NOT NULL,

    erreur          VARCHAR(300),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_appels_ia_fonction ON appels_ia (fonction);
CREATE INDEX IF NOT EXISTS ix_appels_ia_organisation ON appels_ia (organisation_id);
CREATE INDEX IF NOT EXISTS ix_appels_ia_created_at ON appels_ia (created_at);

COMMENT ON TABLE appels_ia IS
    'Journal de consommation des appels de modele. Mesure seulement, ne conditionne rien.';
