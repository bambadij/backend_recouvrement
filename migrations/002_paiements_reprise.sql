-- 002 — Mode de paiement REPRISE + rattrapage des encaissements anterieurs
--
-- Probleme corrige : jusqu'ici, la colonne « montant regle » d'un fichier d'import
-- decrementait montant_restant sans creer de ligne dans « paiements ». Le tableau de
-- bord en tirait deux chiffres contradictoires — le restant tenait compte de ces
-- encaissements, le montant recouvre les ignorait.
--
-- Le code cree desormais un vrai paiement a l'import. Ce script fait deux choses :
--   1. ajoute la valeur REPRISE au type enum mode_paiement ;
--   2. rattrape les creances deja importees, en creant le paiement manquant.
--
-- Usage :
--   docker exec -i postgres psql -v ON_ERROR_STOP=1 -U recouvrement_user \
--     -d recouvrement_db < migrations/002_paiements_reprise.sql
--
-- Sauvegarde prealable :
--   docker exec postgres pg_dump -U recouvrement_user recouvrement_db > sauvegarde.sql

-- ---------------------------------------------------------------------------
-- 1. Nouvelle valeur d'enumeration
--
--    ADD VALUE ne peut pas tourner dans le meme bloc transactionnel que les
--    requetes qui l'utilisent : la valeur ne serait pas encore visible. D'ou
--    cette instruction isolee, avant le BEGIN. IF NOT EXISTS la rend rejouable.
-- ---------------------------------------------------------------------------
ALTER TYPE mode_paiement ADD VALUE IF NOT EXISTS 'REPRISE';

BEGIN;

-- ---------------------------------------------------------------------------
-- 2. Rattrapage
--
--    Pour chaque creance, l'ecart entre ce qui a ete regle (montant_initial -
--    montant_restant) et la somme de ses paiements traces correspond exactement
--    au montant repris a l'import et jamais enregistre. On cree le paiement
--    correspondant, date au jour ou la creance est entree dans l'outil
--    (date_saisie) : la date reelle de l'encaissement n'est nulle part.
--
--    Le script est rejouable : une fois les paiements crees, l'ecart tombe a
--    zero et la requete ne selectionne plus rien.
--
--    Pour voir ce qui sera cree avant d'appliquer :
--      SELECT c.reference, c.montant_initial - c.montant_restant
--             - coalesce((SELECT sum(p.montant) FROM paiements p WHERE p.creance_id = c.id), 0) AS manquant
--      FROM creances c WHERE ... > 0;
-- ---------------------------------------------------------------------------
INSERT INTO paiements (organisation_id, creance_id, montant, date_paiement, mode_paiement, notes, created_at)
SELECT
    c.organisation_id,
    c.id,
    ecart.manquant,
    c.date_saisie,
    'REPRISE',
    'Montant deja regle, repris du fichier d''import (rattrapage retroactif)',
    now()
FROM creances c
CROSS JOIN LATERAL (
    SELECT c.montant_initial - c.montant_restant
           - coalesce((SELECT sum(p.montant) FROM paiements p WHERE p.creance_id = c.id), 0) AS manquant
) AS ecart
WHERE ecart.manquant > 0;

COMMIT;
