-- L13 — les trois rôles : squelette à compléter (étape 1).
-- Vérifier chaque rôle PAR BASCULE (SET ROLE …), jamais en relisant les GRANT.
CREATE ROLE mistral_ingestion LOGIN PASSWORD 'ingestion';
CREATE ROLE mistral_lecture   LOGIN PASSWORD 'lecture';
CREATE ROLE mistral_admin     LOGIN PASSWORD 'admin';

GRANT USAGE ON SCHEMA public TO mistral_ingestion, mistral_lecture, mistral_admin;

-- ingestion : insérer dans mesures et evenements. Rien lire, rien
-- supprimer, ne rien modifier au schéma.
-- À COMPLÉTER :
-- GRANT ……

-- lecture : les mesures et les TROIS niveaux d'agrégats, plus le
-- référentiel (le prédicat de cloisonnement de l'étape 2 consulte
-- affectation_capteur et actifs : le lecteur doit pouvoir les lire).
-- À COMPLÉTER :
-- GRANT ……

-- admin : tout, y compris politiques et jobs.
-- À COMPLÉTER :
-- GRANT ……

-- Le cloisonnement par site (vues security_barrier, REVOKE des accès
-- directs) est l'objet de l'étape 2 : ne pas l'anticiper ici.
