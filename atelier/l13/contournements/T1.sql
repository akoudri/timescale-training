-- T1 — passer par l'agrégat. Sous le rôle de lecture, site 2 : la pyramide
-- laisse-t-elle voir toutes les séries du parc, ou seulement celles du site ?
SET mistral.site = 2;
SET ROLE mistral_lecture;
SELECT 'mistral_1h' AS objet, count(DISTINCT series_id) AS series_visibles FROM mistral_1h;
RESET ROLE;
-- Réussie si le compte est celui du parc entier (490), pas celui du site.
