-- Calcule les bornes depuis le jeu — jamais en dur, jamais now() :
-- la fenêtre du jeu est datée par rapport au calendrier de la formation,
-- pas par rapport au jour où l'atelier est joué.
SELECT min(ts)                          AS debut,
       max(ts) + interval '10 seconds'  AS fin
FROM   mesures \gset

-- une série de vitesse de vent, pour R3 (le libellé fait foi)
SELECT min(af.series_id) AS serie_vent
FROM   affectation_capteur af
JOIN   signaux g ON g.signal_id = af.signal_id
WHERE  g.libelle = 'vitesse_vent_ms' \gset
