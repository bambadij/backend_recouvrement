-- Le montant que le client annonce confier, au moment ou il confie le dossier.
--
-- Ce n'est PAS le montant du dossier : celui-ci reste, ici comme partout
-- ailleurs, la somme des creances saisies. Une colonne totalisee a la main
-- divergerait des la premiere facture ajoutee, corrigee ou soldee, et plus
-- personne ne saurait laquelle des deux croire.
--
-- Ce champ sert a une seule chose : mesurer l'ecart avec la saisie. L'ecole qui
-- annonce « trente impayes, environ 12 M » et dont on a saisi 9,4 M a
-- probablement cinq factures qui manquent. Sans ce reperage, rien ne le dit.
--
-- NULL est le cas courant et n'active rien : sans annonce, aucun ecart n'est
-- affiche.

ALTER TABLE dossiers
    ADD COLUMN IF NOT EXISTS montant_annonce NUMERIC(14, 2);

COMMENT ON COLUMN dossiers.montant_annonce IS
    'Montant annonce par le client. Declaratif, jamais le total du dossier.';
