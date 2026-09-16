-- Schéma cible MISTRAL — squelette à compléter (L02 / M03).
-- Six points de décision. La valeur par défaut n'est pas « la bonne
-- réponse » : c'est la plus courante. Chaque décision attend une phrase
-- de JUSTIFICATION, écrite dans le cadre — pas une validation.
-- Le squelette est exécutable tel quel avec ses valeurs par défaut ; un
-- sous-groupe qui tranche autrement adapte le DDL en conséquence.

-- ┌── DÉCISION 1 ─────────────────────────────────────────────────┐
-- │ Forme du modèle pour `mesures`                                │
-- │   a) étroit        : ts, series_id, valeur                    │
-- │   b) large         : ts, machine_id, une colonne par signal   │
-- │   c) intermédiaire : une hypertable par famille de signaux    │
-- │ Valeur par défaut du squelette : (a)                          │
-- │ JUSTIFICATION : ....................................          │
-- └───────────────────────────────────────────────────────────────┘
-- ┌── DÉCISION 2 ─────────────────────────────────────────────────┐
-- │ Clé d'identification de série                                 │
-- │   a) series_id entier   b) clé composite (site, machine,      │
-- │      signal)            c) tag textuel                        │
-- │ Valeur par défaut du squelette : (a)                          │
-- │ JUSTIFICATION : ....................................          │
-- └───────────────────────────────────────────────────────────────┘
-- ┌── DÉCISION 3 ─────────────────────────────────────────────────┐
-- │ Type de la valeur mesurée                                     │
-- │   a) double precision   b) real   c) numeric                  │
-- │ Valeur par défaut du squelette : (a)                          │
-- │ JUSTIFICATION : ....................................          │
-- └───────────────────────────────────────────────────────────────┘
-- ┌── DÉCISION 4 ─────────────────────────────────────────────────┐
-- │ Emplacement du drapeau de qualité                             │
-- │   a) colonne qualite    b) encodé dans la valeur              │
-- │   c) table séparée                                            │
-- │ Valeur par défaut du squelette : (a)                          │
-- │ JUSTIFICATION : ....................................          │
-- └───────────────────────────────────────────────────────────────┘
-- ┌── DÉCISION 5 ─────────────────────────────────────────────────┐
-- │ Charge utile des événements                                   │
-- │   a) JSONB   b) colonnes typées   c) les deux                 │
-- │ Valeur par défaut du squelette : (a)                          │
-- │ JUSTIFICATION : ....................................          │
-- └───────────────────────────────────────────────────────────────┘
-- ┌── DÉCISION 6 ─────────────────────────────────────────────────┐
-- │ Lien entre une mesure et sa machine                           │
-- │   a) jointure datée sur affectation_capteur                   │
-- │   b) machine_id dénormalisé dans mesures                      │
-- │ Valeur par défaut du squelette : (a)                          │
-- │ JUSTIFICATION : ....................................          │
-- └───────────────────────────────────────────────────────────────┘

-- La ligne de base de M02 reste consultable sous son vrai nom :
ALTER TABLE IF EXISTS mesures RENAME TO mesures_avant;

CREATE TABLE mesures (
    ts        TIMESTAMPTZ      NOT NULL,
    series_id INTEGER          NOT NULL,
    valeur    DOUBLE PRECISION NOT NULL,
    qualite   SMALLINT         NOT NULL DEFAULT 0
) WITH (
    tsdb.hypertable,
    tsdb.partition_column = 'ts',
    tsdb.chunk_interval   = '7 days'   -- valeur du squelette : NE PAS trancher ici, M04 y reviendra avec une mesure
);

-- `evenements` a été restauré en table ordinaire par le parcours amont :
-- la conversion sur place illustre migrate_data (verrouillante — licite
-- ici sur 0,7 M lignes, pas sur une table de production).
SELECT create_hypertable('evenements', by_range('ts', INTERVAL '7 days'),
                         migrate_data => true);

-- Vue « famille production » : le confort du modèle par famille sans en
-- payer le schéma. Utilisée par les requêtes métier de M06/M07.
-- Pas de GROUP BY : une ligne source = une ligne de vue, une seule colonne
-- non NULL — les agrégats (sum, avg) ignorent les NULL, et le planificateur
-- pousse les prédicats. Un pivot par GROUP BY (ts, machine) coûterait des
-- millions de groupes à chaque lecture.
CREATE OR REPLACE VIEW mesures_production AS
SELECT m.ts,
       af.machine_id,
       CASE WHEN g.libelle = 'puissance_kw' THEN m.valeur END AS puissance_kw,
       CASE WHEN g.libelle = 'energie_kwh'  THEN m.valeur END AS energie_kwh
FROM   mesures m
JOIN   affectation_capteur af
  ON   af.series_id = m.series_id
 AND   m.ts >= af.debut AND (af.fin IS NULL OR m.ts < af.fin)
JOIN   signaux g ON g.signal_id = af.signal_id
WHERE  g.libelle IN ('puissance_kw', 'energie_kwh');
