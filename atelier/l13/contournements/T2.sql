-- T2 — utiliser le propriétaire de la table (le compte de la session
-- d'administration), puis le rôle mistral_admin.
RESET ROLE;
SET mistral.site = 2;
SELECT 'proprietaire' AS role, count(DISTINCT series_id) AS series_visibles FROM mesures;
SET ROLE mistral_admin;
SELECT 'mistral_admin' AS role, count(DISTINCT series_id) AS series_visibles FROM mesures;
RESET ROLE;
-- Réussie si l'un des deux voit le parc entier. Question : est-ce corrigeable
-- techniquement, ou est-ce une décision d'organisation à écrire ?
