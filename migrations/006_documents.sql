-- Les pieces d'un dossier : mandat, facture d'origine, recu de paiement.
--
-- Le contenu vit en base, en binaire. Choix assume : le conteneur du backend ne
-- monte aucun volume, des fichiers poses sur son disque disparaitraient au
-- premier redeploiement. Ici la piece est sauvegardee avec la donnee qu'elle
-- justifie, et une restauration ramene les deux dans le meme etat.
--
-- Le prix est une base qui grossit ; deux garde-fous le limitent, cote
-- application : un plafond de 5 Mo par piece, et une colonne chargee seulement
-- au telechargement.

CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,

    dossier_id      INTEGER REFERENCES dossiers(id)  ON DELETE CASCADE,
    creance_id      INTEGER REFERENCES creances(id)  ON DELETE CASCADE,
    paiement_id     INTEGER REFERENCES paiements(id) ON DELETE CASCADE,

    nom             VARCHAR(255) NOT NULL,
    type_mime       VARCHAR(120) NOT NULL,
    taille          INTEGER      NOT NULL,
    contenu         BYTEA        NOT NULL,
    depose_par_nom  VARCHAR(200),

    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),

    -- Exactement un rattachement. Une piece flottante n'aurait pas de contexte,
    -- et une piece rattachee a deux objets serait ambigue a supprimer : la
    -- cascade de l'un effacerait la preuve de l'autre.
    CONSTRAINT ck_documents_un_seul_rattachement CHECK (
        (CASE WHEN dossier_id  IS NOT NULL THEN 1 ELSE 0 END
       + CASE WHEN creance_id  IS NOT NULL THEN 1 ELSE 0 END
       + CASE WHEN paiement_id IS NOT NULL THEN 1 ELSE 0 END) = 1
    )
);

CREATE INDEX IF NOT EXISTS ix_documents_organisation_id ON documents(organisation_id);
CREATE INDEX IF NOT EXISTS ix_documents_dossier_id      ON documents(dossier_id);
CREATE INDEX IF NOT EXISTS ix_documents_creance_id      ON documents(creance_id);
CREATE INDEX IF NOT EXISTS ix_documents_paiement_id     ON documents(paiement_id);
