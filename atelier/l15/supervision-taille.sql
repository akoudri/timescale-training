-- L15 — historique de la taille de la base, pour la TENDANCE de l'alerte A4.
--
-- Une source de données SQL n'a pas de mémoire : Grafana affiche la valeur
-- de pg_database_size() au moment de la requête et n'archive rien. La
-- tendance (« combien de jours restent au rythme actuel ») exige donc un
-- historique tenu DANS LA BASE, par un job — l'action suit le contrat de
-- signature de L10 (job_id, config). Rejouable : ne duplique ni la table
-- ni le job. Fait partie de l'état de reprise mistral-M15.

CREATE TABLE IF NOT EXISTS supervision_taille (
    ts     timestamptz NOT NULL DEFAULT now(),
    octets bigint      NOT NULL
);

CREATE OR REPLACE PROCEDURE relever_taille(job_id int, config jsonb)
LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO supervision_taille (ts, octets)
  VALUES (now(), pg_database_size(current_database()));
  -- 30 jours d'historique suffisent à une pente sur 24 h ; au-delà, purge
  DELETE FROM supervision_taille WHERE ts < now() - interval '30 days';
END $$;

-- un seul job de relevé, même si le fichier est rejoué
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM timescaledb_information.jobs
                 WHERE proc_name = 'relever_taille') THEN
    PERFORM add_job('relever_taille', INTERVAL '1 hour');
  END IF;
END $$;

-- le rôle de supervision (étape 0) doit lire l'historique ; sans lui,
-- l'expression de A4 est vide — le piège des panneaux vides, version A4
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mistral_supervision') THEN
    GRANT SELECT ON supervision_taille TO mistral_supervision;
  END IF;
END $$;

-- premier relevé, par l'ordonnanceur et non par CALL direct (leçon de L10)
SELECT job_id FROM timescaledb_information.jobs
WHERE  proc_name = 'relever_taille' \gset
CALL run_job(:job_id);

SELECT job_id, proc_name, schedule_interval, scheduled, next_start
FROM   timescaledb_information.jobs WHERE proc_name = 'relever_taille';

-- L'expression de A4 : seuil (> 85 % du volume alloué, 200 Go dans le kit)
-- ET tendance (moins de 7 jours restants au rythme des 24 dernières heures,
-- pente par régression linéaire). `jours` est NULL tant qu'il y a moins de
-- deux relevés sur 24 h, et NÉGATIF juste après une purge de rétention :
-- en production, lire « jours BETWEEN 0 AND 7 » — une pente négative n'est
-- pas un danger.
SELECT round(100.0 * o.octets / (200.0 * 1024^3)::numeric, 1)     AS pct_alloue,
       round(t.pente_par_jour / 1024^2)                            AS mo_par_jour,
       round(((200.0 * 1024^3) - o.octets) / nullif(t.pente_par_jour, 0)) AS jours_restants,
       CASE WHEN 100.0 * o.octets / (200.0 * 1024^3) > 85
              OR ((200.0 * 1024^3) - o.octets) / nullif(t.pente_par_jour, 0)
                 BETWEEN 0 AND 7
            THEN 1 ELSE 0 END                                       AS alerte
FROM  (SELECT octets FROM supervision_taille ORDER BY ts DESC LIMIT 1) o,
      (SELECT regr_slope(octets, extract(epoch FROM ts)) * 86400 AS pente_par_jour
       FROM   supervision_taille
       WHERE  ts >= now() - interval '24 hours') t;
