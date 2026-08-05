-- Annulation de 001_client_vers_debiteur.sql
--
-- Remet le schema dans l'etat attendu par la version precedente du backend.
-- Les valeurs de numero_facture et date_facture sont perdues (colonnes supprimees) ;
-- les numeros de facture restent dans "reference", d'ou ils avaient ete recopies.

BEGIN;

DROP INDEX IF EXISTS ix_creances_numero_facture;
ALTER TABLE creances DROP COLUMN date_facture;
ALTER TABLE creances DROP COLUMN numero_facture;

ALTER TABLE creances RENAME COLUMN date_saisie TO date_creation;

ALTER TABLE creances RENAME CONSTRAINT creances_debiteur_id_fkey TO creances_client_id_fkey;
ALTER INDEX ix_creances_debiteur_id RENAME TO ix_creances_client_id;
ALTER TABLE creances RENAME COLUMN debiteur_id TO client_id;

ALTER TABLE debiteurs RENAME CONSTRAINT debiteurs_organisation_id_fkey TO clients_organisation_id_fkey;
ALTER TABLE debiteurs RENAME CONSTRAINT uq_debiteurs_organisation_email TO uq_clients_organisation_email;
ALTER INDEX ix_debiteurs_organisation_id RENAME TO ix_clients_organisation_id;
ALTER INDEX debiteurs_pkey RENAME TO clients_pkey;
ALTER SEQUENCE debiteurs_id_seq RENAME TO clients_id_seq;
ALTER TABLE debiteurs RENAME TO clients;

COMMIT;
