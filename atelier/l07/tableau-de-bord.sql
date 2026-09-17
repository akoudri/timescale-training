-- Les quatre requêtes du tableau de bord MISTRAL, telles qu'elles tournent
-- sur le brut (L07 étape 4 : mesurer, puis écrire l07/tableau-de-bord-pyramide.sql
-- — les mêmes requêtes servies par le bon niveau — et mesurer à nouveau).
-- Bornes :debut / :fin : \i l05/bornes.sql au préalable.

-- Q1 — puissance moyenne du parc par heure, 7 derniers jours
SELECT time_bucket(INTERVAL '1 hour', m.ts) AS heure, avg(m.valeur) AS kw
FROM   mesures m
JOIN   affectation_capteur af ON af.series_id = m.series_id
JOIN   signaux g ON g.signal_id = af.signal_id AND g.libelle = 'puissance_kw'
WHERE  m.ts >= :'fin'::timestamptz - interval '7 days' AND m.ts < :'fin'
GROUP  BY 1 ORDER BY 1;

-- Q2 — énergie produite par jour (Europe/Paris), fenêtre complète
SELECT time_bucket(INTERVAL '1 day', m.ts, 'Europe/Paris') AS jour,
       sum(m.valeur) / 360.0 AS kwh
FROM   mesures m
JOIN   affectation_capteur af ON af.series_id = m.series_id
JOIN   signaux g ON g.signal_id = af.signal_id AND g.libelle = 'puissance_kw'
WHERE  m.ts >= :'debut' AND m.ts < :'fin'
GROUP  BY 1 ORDER BY 1;

-- Q3 — puissance maximale par machine, 30 derniers jours (top 10)
SELECT af.machine_id, max(m.valeur) AS kw_max
FROM   mesures m
JOIN   affectation_capteur af ON af.series_id = m.series_id
JOIN   signaux g ON g.signal_id = af.signal_id AND g.libelle = 'puissance_kw'
WHERE  m.ts >= :'fin'::timestamptz - interval '30 days' AND m.ts < :'fin'
GROUP  BY 1 ORDER BY 2 DESC LIMIT 10;

-- Q4 — volumétrie : points reçus par jour (Europe/Paris), toutes séries
SELECT time_bucket(INTERVAL '1 day', ts, 'Europe/Paris') AS jour, count(*) AS points
FROM   mesures
WHERE  ts >= :'debut' AND ts < :'fin'
GROUP  BY 1 ORDER BY 1;
