-- 005 — Forme canonique du telephone, pour le dedoublonnage des debiteurs
--
-- Le dedoublonnage a l'import comparait le telephone caractere par caractere,
-- espaces retires. « +221 77 000 11 11 », « 00221770001111 » et « 770001111 »
-- creaient donc trois fiches pour la meme personne.
--
-- On stocke desormais une forme canonique a cote du numero saisi : chiffres
-- seuls, prefixe international retire, 9 derniers chiffres. C'est elle qui sert
-- a comparer ; « telephone » reste affiche tel que l'utilisateur l'a ecrit.
--
-- Usage :
--   docker exec -i postgres psql -v ON_ERROR_STOP=1 -U recouvrement_user \
--     -d recouvrement_db < migrations/005_telephone_normalise.sql

BEGIN;

ALTER TABLE debiteurs ADD COLUMN IF NOT EXISTS telephone_normalise VARCHAR(20);

-- Reprise des numeros deja saisis. La logique reproduit exactement celle de
-- app/debiteurs/telephone.py : si les deux divergent, le dedoublonnage devient
-- incoherent entre les lignes reprises et les nouvelles.
UPDATE debiteurs d
SET telephone_normalise = nullif(
        CASE WHEN length(sans_prefixe) > 9 THEN right(sans_prefixe, 9) ELSE sans_prefixe END,
        ''
    )
FROM (
    SELECT
        id,
        CASE
            WHEN left(chiffres, 2) = '00' THEN substr(chiffres, 3)
            ELSE chiffres
        END AS sans_prefixe
    FROM (
        SELECT id, regexp_replace(coalesce(telephone, ''), '\D', '', 'g') AS chiffres
        FROM debiteurs
    ) AS x
) AS calcul
WHERE calcul.id = d.id;

CREATE INDEX IF NOT EXISTS ix_debiteurs_telephone_normalise ON debiteurs (telephone_normalise);

COMMIT;
