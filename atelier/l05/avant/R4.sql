-- R4 avant — comparaison d'un mois avec le mois précédent.
-- Deux défauts : l'agrégation est calculée deux fois, et le découpage
-- mensuel souffre du même problème de fuseau que R2.
SELECT m1.mois, m1.energie, m2.energie AS mois_precedent
FROM   ( SELECT date_trunc('month', ts) AS mois, sum(puissance_kw) / 360.0 AS energie
         FROM mesures_production GROUP BY 1 ) m1
LEFT   JOIN ( SELECT date_trunc('month', ts) AS mois, sum(puissance_kw) / 360.0 AS energie
              FROM mesures_production GROUP BY 1 ) m2
  ON   m2.mois = m1.mois - INTERVAL '1 month';
