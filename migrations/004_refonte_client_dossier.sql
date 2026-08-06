-- 004 — Refonte : client, creancier, dossier
--
-- Le modele metier reel, tel qu'il ressort du fichier de suivi des dossiers :
--
--   Client     : celui qui confie la demande (l'ecole, la pharmacie, ACREMAC)
--   Creancier  : celui a qui l'argent est du. Souvent le client lui-meme, et le
--                dossier laisse alors creancier_id a NULL
--   Dossier    : la demande referencee. Sa reference vient du client, ses
--                formats varient, elle peut manquer. Un dossier porte PLUSIEURS
--                debiteurs — une ecole confie trente etudiants en une fois
--   Debiteur   : qui doit. Rattache a la facture, pas au dossier
--   Creance    : la facture. Numero et date de facture, montant, echeance
--
-- Les relances et les promesses visent un debiteur A L'INTERIEUR d'un dossier :
-- on ne relance ni « le dossier » (trente etudiants d'un coup) ni facture par
-- facture (quatre courriers au meme debiteur).
--
-- ATTENTION — ce script SUPPRIME toutes les donnees metier. Il a ete demande
-- explicitement : le modele precedent ne correspondait pas au metier et les
-- donnees seront ressaisies. Organisations et utilisateurs sont conserves.
--
-- Les tables ne sont pas recreees ici : le create_all de l'application les
-- reconstruit au demarrage a partir des modeles SQLAlchemy. C'est volontaire —
-- reecrire le DDL a la main garantirait une derive avec l'ORM.
--
-- Usage :
--   docker exec postgres pg_dump -U recouvrement_user recouvrement_db > sauvegarde.sql
--   docker exec -i postgres psql -v ON_ERROR_STOP=1 -U recouvrement_user \
--     -d recouvrement_db < migrations/004_refonte_client_dossier.sql
--   puis redemarrer le backend : il recree les tables vides.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Garde-fou : on ne vide pas une base par accident
--
--    Le script refuse de tourner si les tables metier sont deja vides ET que le
--    nouveau schema est en place — signe qu'il a deja ete applique.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    IF to_regclass('public.creances') IS NOT NULL
       AND EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_name = 'dossiers' AND column_name = 'client_id'
       )
       AND (SELECT count(*) FROM public.creances) = 0
    THEN
        RAISE EXCEPTION 'Le nouveau schema est deja en place et les creances sont vides : rien a faire.';
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- 2. Suppression des tables metier
--
--    CASCADE emporte les cles etrangeres entre elles ; l'ordre n'a donc pas
--    d'importance, mais on va des feuilles vers les racines par lisibilite.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS promesses CASCADE;
DROP TABLE IF EXISTS segmentations CASCADE;
DROP TABLE IF EXISTS relances CASCADE;
DROP TABLE IF EXISTS paiements CASCADE;
DROP TABLE IF EXISTS creances CASCADE;
DROP TABLE IF EXISTS dossiers CASCADE;
DROP TABLE IF EXISTS creanciers CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS debiteurs CASCADE;

-- ---------------------------------------------------------------------------
-- 3. Les types enum survivent a DROP TABLE
--
--    Sans cela, create_all echouerait sur « type deja existant ». role_utilisateur
--    n'est pas dans la liste : la table users est conservee et l'utilise.
-- ---------------------------------------------------------------------------
DROP TYPE IF EXISTS statut_creance;
DROP TYPE IF EXISTS mode_paiement;
DROP TYPE IF EXISTS type_relance;
DROP TYPE IF EXISTS statut_relance;
DROP TYPE IF EXISTS statut_promesse;
DROP TYPE IF EXISTS source_promesse;
DROP TYPE IF EXISTS statut_dossier;
DROP TYPE IF EXISTS type_dossier;
DROP TYPE IF EXISTS objectif_dossier;
DROP TYPE IF EXISTS segment_risque;
DROP TYPE IF EXISTS potentiel_recouvrement;

COMMIT;
