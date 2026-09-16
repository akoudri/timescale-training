-- Volumes après application de la chaîne — l'économie nette déduit le
-- volume ajouté par la pyramide.
SELECT 'mesures (hypertable)' AS objet, pg_size_pretty(hypertable_size('mesures')) AS volume
UNION ALL
SELECT 'pyramide 1min',
       pg_size_pretty(hypertable_size(format('%I.%I', materialization_hypertable_schema,
                                             materialization_hypertable_name)::regclass))
FROM   timescaledb_information.continuous_aggregates WHERE view_name = 'mistral_1min'
UNION ALL
SELECT 'pyramide 1h',
       pg_size_pretty(hypertable_size(format('%I.%I', materialization_hypertable_schema,
                                             materialization_hypertable_name)::regclass))
FROM   timescaledb_information.continuous_aggregates WHERE view_name = 'mistral_1h'
UNION ALL
SELECT 'pyramide 1j',
       pg_size_pretty(hypertable_size(format('%I.%I', materialization_hypertable_schema,
                                             materialization_hypertable_name)::regclass))
FROM   timescaledb_information.continuous_aggregates WHERE view_name = 'mistral_1j';
