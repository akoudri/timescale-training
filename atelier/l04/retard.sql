-- Retard d'arrivée : la seule valeur de M05 dont un autre module dépend
-- structurellement (M08 dimensionne ses fenêtres de rafraîchissement avec).
SELECT percentile_disc(0.50) WITHIN GROUP (ORDER BY ingere_le - ts) AS p50,
       percentile_disc(0.95) WITHIN GROUP (ORDER BY ingere_le - ts) AS p95,
       percentile_disc(0.99) WITHIN GROUP (ORDER BY ingere_le - ts) AS p99,
       max(ingere_le - ts)                                          AS pire
FROM   mesures_charge;
