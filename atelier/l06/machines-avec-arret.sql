-- L06 — machines et mois comportant un arrêt de maintenance long
-- (pas d'échantillonnage passé à l'heure pendant l'arrêt : c'est là que
-- moyenne naïve et moyenne pondérée par le temps divergent).
-- Dérivé de machines-avec-arret.json, livré par le générateur.
SELECT * FROM (VALUES
    (15, 'site 1', timestamptz '2026-10-03T01:32:00Z', timestamptz '2026-10-04T19:54:30Z', 'octobre 2026'),
    (28, 'site 2', timestamptz '2026-10-07T00:45:20Z', timestamptz '2026-10-08T19:35:40Z', 'octobre 2026'),
    (42, 'site 3', timestamptz '2026-10-11T03:54:10Z', timestamptz '2026-10-12T23:47:00Z', 'octobre 2026')
) AS arrets(machine_id, site, debut, fin, mois);
