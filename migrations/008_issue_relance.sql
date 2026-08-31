-- Ce qu'une relance a produit, en quatre valeurs exclusives.
--
-- Jusqu'ici, l'unique trace d'un retour etait « resultat », du texte libre. Le
-- champ n'etait saisissable que tant que la relance restait PLANIFIEE — donc au
-- seul moment ou l'agent ne peut rien savoir, puisque rien n'est parti. Une fois
-- marquee envoyee, la relance n'etait plus annotable. Resultat mesure : sur les
-- douze relances de la base, zero comptait un retour.
--
-- Cinq fonctions en dependaient en silence : le critere « sans reponse » (qui
-- retenait donc tout le monde), l'extraction des promesses (qui n'avait aucune
-- entree), le taux de reponse par debiteur, l'assistant, et la segmentation.
--
-- NULL signifie « pas encore annotee » et ne se confond pas avec SANS_REPONSE :
-- ne pas savoir n'est pas savoir que personne n'a repondu.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'issue_relance') THEN
        CREATE TYPE issue_relance AS ENUM (
            'A_PROMIS', 'A_REPONDU', 'SANS_REPONSE', 'REFUSE'
        );
    END IF;
END$$;

ALTER TABLE relances
    ADD COLUMN IF NOT EXISTS issue issue_relance;

-- Les relances passees restent a NULL : leur issue n'a jamais ete recueillie et
-- l'inventer fausserait les taux de reponse qu'on cherche precisement a etablir.
CREATE INDEX IF NOT EXISTS ix_relances_issue ON relances (issue);

COMMENT ON COLUMN relances.issue IS
    'Ce que la relance a produit. NULL = pas encore annotee, distinct de SANS_REPONSE.';
