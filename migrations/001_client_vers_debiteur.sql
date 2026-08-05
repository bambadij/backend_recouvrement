-- 001 — Renommage Client -> Debiteur + metadonnees de facturation
--
-- Pourquoi ce script : l'application cree son schema avec Base.metadata.create_all(),
-- qui ne sait que CREER des tables manquantes. Il ne renomme rien et n'ajoute aucune
-- colonne a une table existante. Sur une base qui contient deja des donnees, il faut
-- donc appliquer ce script AVANT de demarrer la nouvelle version du backend, sinon
-- l'app tournera contre un schema incompatible (colonne debiteur_id absente).
--
-- Usage :
--   docker exec -i postgres psql -U recouvrement_user -d recouvrement_db \
--     < migrations/001_client_vers_debiteur.sql
--
-- Le script est transactionnel : en cas d'erreur, rien n'est applique.
-- Faire une sauvegarde avant :
--   docker exec postgres pg_dump -U recouvrement_user recouvrement_db > sauvegarde.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. Cas frequent : l'application a demarre AVANT la migration.
--
--    Son create_all() a alors cree une table "debiteurs" vide, qui empeche le
--    renommage de "clients". On la supprime — mais seulement si elle est vide :
--    si elle contient des lignes, c'est que la migration a deja tourne et il ne
--    faut surtout pas ecraser les donnees.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF to_regclass('public.debiteurs') IS NOT NULL THEN
        IF (SELECT count(*) FROM public.debiteurs) > 0 THEN
            RAISE EXCEPTION
                'La table "debiteurs" existe deja et contient des donnees : migration deja appliquee, rien a faire.';
        END IF;
        DROP TABLE public.debiteurs;
        RAISE NOTICE 'Table "debiteurs" vide (creee par create_all) supprimee avant le renommage.';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 1. La table des debiteurs (ceux qui doivent de l'argent) s'appelait "clients"
-- ---------------------------------------------------------------------------
ALTER TABLE clients RENAME TO debiteurs;
ALTER SEQUENCE clients_id_seq RENAME TO debiteurs_id_seq;
ALTER INDEX clients_pkey RENAME TO debiteurs_pkey;
ALTER INDEX ix_clients_organisation_id RENAME TO ix_debiteurs_organisation_id;
ALTER TABLE debiteurs RENAME CONSTRAINT uq_clients_organisation_email TO uq_debiteurs_organisation_email;
ALTER TABLE debiteurs RENAME CONSTRAINT clients_organisation_id_fkey TO debiteurs_organisation_id_fkey;

-- ---------------------------------------------------------------------------
-- 2. La cle etrangere cote creances suit
-- ---------------------------------------------------------------------------
ALTER TABLE creances RENAME COLUMN client_id TO debiteur_id;
ALTER INDEX ix_creances_client_id RENAME TO ix_creances_debiteur_id;
ALTER TABLE creances RENAME CONSTRAINT creances_client_id_fkey TO creances_debiteur_id_fkey;

-- ---------------------------------------------------------------------------
-- 3. date_creation designait la date de SAISIE dans l'outil, pas la date de la
--    creance. On la renomme pour liberer la notion de date de facture.
-- ---------------------------------------------------------------------------
ALTER TABLE creances RENAME COLUMN date_creation TO date_saisie;

-- ---------------------------------------------------------------------------
-- 4. Metadonnees de facturation
--    date_facture est nullable : les reprises de stock ne l'ont pas toujours,
--    et une date inventee fausserait l'anciennete et les interets de retard.
-- ---------------------------------------------------------------------------
ALTER TABLE creances ADD COLUMN numero_facture VARCHAR(50);
ALTER TABLE creances ADD COLUMN date_facture DATE;
CREATE INDEX ix_creances_numero_facture ON creances (numero_facture);

-- ---------------------------------------------------------------------------
-- 5. Recuperation des numeros de facture deja presents dans "reference"
--
--    Avant ce changement, l'import ecrivait le numero de facture du fichier
--    source directement dans "reference". Les references generees par le backend,
--    elles, sont prefixees par les 3 premieres lettres du nom de l'organisation
--    (ex. organisation "ISM" -> "ISM-2026-0002"). Tout ce qui ne porte pas ce
--    prefixe vient donc d'un fichier client : c'est un vrai numero de facture.
--
--    Pour verifier ce que la requete va toucher avant de l'appliquer :
--      SELECT o.nom, c.reference FROM creances c JOIN organisations o ON o.id = c.organisation_id
--      WHERE c.reference NOT LIKE upper(left(regexp_replace(o.nom, '[^A-Za-z]', '', 'g'), 3)) || '-%';
-- ---------------------------------------------------------------------------
UPDATE creances c
SET numero_facture = c.reference
FROM organisations o
WHERE o.id = c.organisation_id
  AND c.reference NOT LIKE upper(left(regexp_replace(o.nom, '[^A-Za-z]', '', 'g'), 3)) || '-%';

COMMIT;
