-- Segmentation IA : colonnes de contexte sur les creances.
--
-- POURQUOI CE FICHIER EXISTE
-- Le demarrage applique Base.metadata.create_all (voir main.py), qui cree les
-- tables manquantes mais n'ajoute JAMAIS de colonne a une table existante. Les
-- nouvelles tables (promesses, segmentations) et leurs types enum sont donc
-- crees automatiquement ; les trois colonnes ci-dessous ne le sont pas sur une
-- base deja en service. A jouer une fois, avant de redemarrer l'API.
--
--   psql "$DATABASE_URL" -f migrations/2026-07-31_segmentation.sql
--
-- Idempotent : rejouable sans erreur, y compris sur une base neuve ou
-- create_all a deja cree les colonnes.
--
-- Ceci est un correctif ponctuel, pas un remplacement d'Alembic : le projet
-- devra toujours passer a des migrations versionnees (cf. le TODO de main.py).

ALTER TABLE creances ADD COLUMN IF NOT EXISTS etablissement VARCHAR(255);
ALTER TABLE creances ADD COLUMN IF NOT EXISTS cycle VARCHAR(100);
ALTER TABLE creances ADD COLUMN IF NOT EXISTS financeur VARCHAR(255);

CREATE INDEX IF NOT EXISTS ix_creances_etablissement ON creances (etablissement);
CREATE INDEX IF NOT EXISTS ix_creances_cycle ON creances (cycle);
CREATE INDEX IF NOT EXISTS ix_creances_financeur ON creances (financeur);

-- Auteur de la relance, pour la productivite par agent. Instantane du nom plutot
-- qu'une cle etrangere : la productivite passee ne doit pas bouger si un compte
-- est renomme ou supprime. Nul sur les relances anterieures, qui resteront donc
-- hors des statistiques par agent — c'est assume, on ne peut pas leur inventer
-- un auteur.
ALTER TABLE relances ADD COLUMN IF NOT EXISTS cree_par_nom VARCHAR(200);
CREATE INDEX IF NOT EXISTS ix_relances_cree_par_nom ON relances (cree_par_nom);
