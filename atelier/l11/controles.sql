-- L11 — les trois contrôles de cohérence. À exécuter des deux côtés
-- (source : legacy/mistral_legacy ; cible : timescaledb/mistral_prod)
-- et à comparer. Comptages et sommes SUR ENTIERS : une somme de flottants
-- diverge dès que l'ordre d'agrégation diffère entre les deux instances.

-- Contrôle 1 — comptage global (détecte une copie tronquée)
SELECT count(*) AS lignes FROM mesures;

-- Contrôle 2 — somme par période (détecte trous et décalages)
SELECT date_trunc('day', ts) AS jour, count(*) AS n, sum(series_id) AS somme_sid
FROM   mesures GROUP BY 1 ORDER BY 1;

-- Contrôle 3 — échantillonnage : cent lignes comparées champ par champ
-- (l'échantillon est déterministe : mêmes id des deux côtés)
SELECT id, ts, series_id, valeur, qualite
FROM   mesures
WHERE  id % 414719 = 1
ORDER  BY id LIMIT 100;
