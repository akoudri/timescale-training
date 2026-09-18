-- L11 — les trois contrôles de cohérence. À exécuter des deux côtés
-- (source : legacy/mistral_legacy ; cible : timescaledb/mistral_prod)
-- et à comparer. Comptages et sommes SUR ENTIERS : une somme de flottants
-- diverge dès que l'ordre d'agrégation diffère entre les deux instances.

-- Contrôle 1 — comptage global (détecte une copie tronquée)
SELECT count(*) AS lignes FROM mesures;

-- Contrôle 2 — somme par période (détecte trous et décalages)
SELECT date_trunc('day', ts) AS jour, count(*) AS n, sum(series_id) AS somme_sid
FROM   mesures GROUP BY 1 ORDER BY 1;

-- Contrôle 3 — échantillonnage : une centaine de lignes comparées champ
-- par champ. L'échantillon est déterministe (même hachage des deux côtés,
-- hashint8 est identique en PG 16 et 17) et RÉPARTI sur toute la fenêtre.
-- Pourquoi un hachage et pas `id % N = 1` : l'identifiant de la legacy est
-- structuré (un bloc de 103 680 minutes par série) ; un modulo proche
-- d'un multiple de la taille de bloc tombe toujours sur les mêmes
-- séries et les mêmes minutes — cent lignes des deux dernières heures du
-- dernier jour, et rien de juillet ni d'août. Un échantillon « au hasard »
-- se vérifie : plage de ts et nombre de séries couvertes.
SELECT id, ts, series_id, valeur, qualite
FROM   mesures
WHERE  mod(hashint8(id), 414719) = 0
ORDER  BY id;
-- couverture de l'échantillon (à lire avant de comparer)
SELECT count(*) AS lignes, count(DISTINCT series_id) AS series,
       min(ts), max(ts)
FROM   mesures WHERE mod(hashint8(id), 414719) = 0;
