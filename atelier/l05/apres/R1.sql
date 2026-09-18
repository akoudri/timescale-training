-- R1 après. Nœud responsable du gain : aucun spectaculaire — la requête
-- portait déjà un prédicat temporel, l'exclusion de chunks jouait déjà.
-- Les corrections sont de JUSTESSE, pas de vitesse :
--   1. time_bucket (sargable, composable) au lieu de date_trunc ;
--   2. jointure DATÉE sur debut/fin — sans elle, une série réaffectée
--      produit deux lignes par point et fausse l'historique ;
--   3. la « production » ne somme plus que puissance_kw — l'avant
--      additionnait kW, kWh, degrés et tours/minute dans le même sum().
SELECT a.site_id,
       time_bucket(INTERVAL '1 hour', m.ts) AS heure,
       sum(m.valeur)                        AS production_kw
FROM   mesures m
JOIN   affectation_capteur af
  ON   af.series_id = m.series_id
 AND   m.ts >= af.debut AND (af.fin IS NULL OR m.ts < af.fin)
JOIN   signaux g ON g.signal_id = af.signal_id AND g.libelle = 'puissance_kw'
JOIN   actifs  a ON a.machine_id = af.machine_id
WHERE  m.ts >= :'fin'::timestamptz - interval '30 days' AND m.ts < :'fin'
GROUP  BY 1, 2;
