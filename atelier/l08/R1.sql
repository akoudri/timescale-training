-- R1 — point le plus récent d'une série
SELECT * FROM {{table}}
WHERE  series_id = 137
ORDER  BY ts DESC LIMIT 1;
