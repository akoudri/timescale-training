-- Chargement du jeu complet (45 jours, ~190 M lignes) dans l'hypertable,
-- par COPY binaire — le mode de chargement que la formation enseigne (M05).
-- Compter quelques minutes sur l'instance épinglée.
\timing on
\copy mesures FROM '/jeux/mesures.bin' WITH (FORMAT binary)
\timing off
SELECT count(*) AS lignes_chargees FROM mesures;
