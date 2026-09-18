-- R4 après. Nœuds responsables : une seule agrégation (CTE) au lieu de
-- deux sous-requêtes identiques — le plan ne contient plus qu'un parcours —
-- et lag() pour le décalage. Le seau mensuel est de largeur variable et
-- porte le fuseau : la leçon de R2 s'applique aussi aux mois.
WITH mensuel AS (
    SELECT time_bucket(INTERVAL '1 month', ts, 'Europe/Paris') AS mois,
           sum(puissance_kw) / 360.0                           AS energie
    FROM   mesures_production
    WHERE  ts >= :'debut' AND ts < :'fin'
    GROUP  BY 1
)
SELECT mois, energie,
       lag(energie) OVER (ORDER BY mois) AS mois_precedent
FROM   mensuel ORDER BY mois;
