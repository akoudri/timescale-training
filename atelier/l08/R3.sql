-- R3 — agrégation sur toute la fenêtre, sans filtre de série
SELECT avg(valeur), count(*) FROM {{table}};
