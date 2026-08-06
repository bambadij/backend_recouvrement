-- 003 — Creanciers et dossiers
--
-- Introduit les deux entites manquantes du metier :
--   * creancier : le donneur d'ordre, celui pour qui on recouvre ;
--   * dossier   : le mandat, soit 1 creancier + 1 debiteur + N factures.
--
-- Et deplace la maille de relance : on relance un dossier, pas une facture. Les
-- promesses suivent, puisqu'elles sont extraites des relances.
--
-- Reprise des donnees existantes :
--   1. un creancier « interne » par organisation, qui la represente elle-meme ;
--   2. un dossier par couple (creancier interne, debiteur) — les factures d'un
--      meme debiteur se retrouvent donc regroupees, ce qui est tout l'interet ;
--   3. les relances et les promesses sont rebranchees sur le dossier de leur
--      creance d'origine.
--
-- Usage :
--   docker exec -i postgres psql -v ON_ERROR_STOP=1 -U recouvrement_user \
--     -d recouvrement_db < migrations/003_creanciers_et_dossiers.sql
--
-- Sauvegarde prealable imperative :
--   docker exec postgres pg_dump -U recouvrement_user recouvrement_db > sauvegarde.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Tables vides eventuellement creees par create_all avant la migration
--
--    Meme precaution qu'en 001 : si l'application a demarre sur le nouveau code,
--    elle a cree des tables vides qui empechent de creer les vraies. On ne les
--    supprime que si elles sont vides.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF to_regclass('public.dossiers') IS NOT NULL THEN
        IF (SELECT count(*) FROM public.dossiers) > 0 THEN
            RAISE EXCEPTION 'La table "dossiers" contient deja des donnees : migration deja appliquee ?';
        END IF;
        DROP TABLE public.dossiers CASCADE;
    END IF;
    -- Le type enum survit a DROP TABLE : sans cela, le CREATE TYPE plus bas
    -- echoue avec « type statut_dossier already exists ».
    DROP TYPE IF EXISTS statut_dossier;
    IF to_regclass('public.creanciers') IS NOT NULL THEN
        IF (SELECT count(*) FROM public.creanciers) > 0 THEN
            RAISE EXCEPTION 'La table "creanciers" contient deja des donnees : migration deja appliquee ?';
        END IF;
        DROP TABLE public.creanciers CASCADE;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1. Les deux nouvelles tables
-- ---------------------------------------------------------------------------
CREATE TABLE creanciers (
    id              SERIAL PRIMARY KEY,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    nom             VARCHAR(255) NOT NULL,
    code            VARCHAR(8)   NOT NULL,
    email           VARCHAR(255),
    telephone       VARCHAR(30),
    adresse         VARCHAR(255),
    notes           VARCHAR(1000),
    is_interne      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_creanciers_organisation_code UNIQUE (organisation_id, code)
);
CREATE INDEX ix_creanciers_organisation_id ON creanciers (organisation_id);
CREATE INDEX ix_creanciers_code ON creanciers (code);

CREATE TYPE statut_dossier AS ENUM ('OUVERT', 'CLOS');

CREATE TABLE dossiers (
    id              SERIAL PRIMARY KEY,
    organisation_id INTEGER NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
    creancier_id    INTEGER NOT NULL REFERENCES creanciers(id) ON DELETE CASCADE,
    debiteur_id     INTEGER NOT NULL REFERENCES debiteurs(id) ON DELETE CASCADE,
    numero          VARCHAR(50) NOT NULL,
    statut          statut_dossier NOT NULL DEFAULT 'OUVERT',
    notes           VARCHAR(1000),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_dossiers_organisation_numero UNIQUE (organisation_id, numero)
);
CREATE INDEX ix_dossiers_organisation_id ON dossiers (organisation_id);
CREATE INDEX ix_dossiers_creancier_id ON dossiers (creancier_id);
CREATE INDEX ix_dossiers_debiteur_id ON dossiers (debiteur_id);
CREATE INDEX ix_dossiers_numero ON dossiers (numero);

-- ---------------------------------------------------------------------------
-- 2. Un creancier interne par organisation
--
--    Le code sert de prefixe aux numeros de dossier : 4 premieres lettres du nom
--    de l'organisation, sans accents ni ponctuation. « ISM » -> ISM.
-- ---------------------------------------------------------------------------
INSERT INTO creanciers (organisation_id, nom, code, is_interne)
SELECT
    o.id,
    o.nom,
    coalesce(nullif(upper(left(regexp_replace(o.nom, '[^A-Za-z0-9]', '', 'g'), 4)), ''), 'CRE' || o.id),
    true
FROM organisations o;

-- ---------------------------------------------------------------------------
-- 3. Un dossier par couple (creancier interne, debiteur) ayant des creances
--
--    row_number donne la sequence par creancier, comme le fait le service pour
--    les dossiers crees ensuite. L'annee est celle de la migration.
-- ---------------------------------------------------------------------------
INSERT INTO dossiers (organisation_id, creancier_id, debiteur_id, numero)
SELECT
    x.organisation_id,
    x.creancier_id,
    x.debiteur_id,
    x.code || '-' || extract(year FROM current_date)::int || '-'
        || lpad(row_number() OVER (PARTITION BY x.creancier_id ORDER BY x.debiteur_id)::text, 5, '0')
FROM (
    SELECT DISTINCT c.organisation_id, cr.id AS creancier_id, cr.code, c.debiteur_id
    FROM creances c
    JOIN creanciers cr ON cr.organisation_id = c.organisation_id AND cr.is_interne
) AS x;

-- ---------------------------------------------------------------------------
-- 4. Rattachement des creances
--
--    NOT NULL pose apres remplissage : la colonne est ajoutee nullable, remplie,
--    puis contrainte. RESTRICT sur la cle etrangere — supprimer un dossier ne
--    doit jamais faire disparaitre des impayes.
-- ---------------------------------------------------------------------------
ALTER TABLE creances ADD COLUMN dossier_id INTEGER;

UPDATE creances c
SET dossier_id = d.id
FROM dossiers d
WHERE d.organisation_id = c.organisation_id AND d.debiteur_id = c.debiteur_id;

ALTER TABLE creances ALTER COLUMN dossier_id SET NOT NULL;
ALTER TABLE creances ADD CONSTRAINT creances_dossier_id_fkey
    FOREIGN KEY (dossier_id) REFERENCES dossiers(id) ON DELETE RESTRICT;
CREATE INDEX ix_creances_dossier_id ON creances (dossier_id);

-- ---------------------------------------------------------------------------
-- 5. Relances : de la facture au dossier
--
--    Chaque relance suit le dossier de la creance qu'elle visait. Plusieurs
--    relances portant sur des factures d'un meme debiteur se retrouvent donc sur
--    le meme dossier : c'est le regroupement voulu, l'historique est reconstitue.
-- ---------------------------------------------------------------------------
ALTER TABLE relances ADD COLUMN dossier_id INTEGER;

UPDATE relances r
SET dossier_id = c.dossier_id
FROM creances c
WHERE c.id = r.creance_id;

ALTER TABLE relances ALTER COLUMN dossier_id SET NOT NULL;
ALTER TABLE relances ADD CONSTRAINT relances_dossier_id_fkey
    FOREIGN KEY (dossier_id) REFERENCES dossiers(id) ON DELETE CASCADE;
CREATE INDEX ix_relances_dossier_id ON relances (dossier_id);

ALTER TABLE relances DROP COLUMN creance_id;

-- ---------------------------------------------------------------------------
-- 6. Promesses : meme bascule, elles sont extraites des relances
-- ---------------------------------------------------------------------------
ALTER TABLE promesses ADD COLUMN dossier_id INTEGER;

UPDATE promesses p
SET dossier_id = c.dossier_id
FROM creances c
WHERE c.id = p.creance_id;

-- Une promesse dont la creance a disparu n'a plus de rattachement possible :
-- il n'y en a pas aujourd'hui, mais on echoue bruyamment plutot que d'inventer.
DO $$
DECLARE orphelines INTEGER;
BEGIN
    SELECT count(*) INTO orphelines FROM promesses WHERE dossier_id IS NULL;
    IF orphelines > 0 THEN
        RAISE EXCEPTION 'ATTENTION : % promesse(s) sans creance rattachable, migration interrompue', orphelines;
    END IF;
END $$;

ALTER TABLE promesses ALTER COLUMN dossier_id SET NOT NULL;
ALTER TABLE promesses ADD CONSTRAINT promesses_dossier_id_fkey
    FOREIGN KEY (dossier_id) REFERENCES dossiers(id) ON DELETE CASCADE;
CREATE INDEX ix_promesses_dossier_id ON promesses (dossier_id);

ALTER TABLE promesses DROP COLUMN creance_id;

COMMIT;
