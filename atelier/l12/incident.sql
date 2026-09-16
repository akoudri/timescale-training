-- L12 — la suppression accidentelle. Relève l'instant AVANT de supprimer.
--
-- La fenêtre supprimée se calcule de max(ts) — jamais de now() : le jeu
-- est daté, le comportement doit être identique quel que soit le jour.
-- Elle porte sur les TROIS derniers jours (zone rowstore) : sur une base
-- dont l'historique est basculé en columnstore, un DELETE qui traverse
-- les chunks compressés échoue sur la limite de décompression DML — la
-- compression protège, de fait, l'historique froid des suppressions
-- accidentelles massives (voir errata : l'énoncé originel disait 21 j).
SELECT now() AS instant_avant_incident \gset
\echo === INSTANT AVANT INCIDENT (à noter) : :instant_avant_incident

SELECT max(ts) - interval '3 days' AS coupure FROM mesures \gset

DELETE FROM mesures WHERE ts >= :'coupure';

SELECT count(*) AS lignes_restantes, min(ts), max(ts) FROM mesures;
