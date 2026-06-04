-- Validate Bronze layer: row counts, null rates, dedup identity
-- Run via: docker exec trino trino --catalog iceberg < infra/trino/sql/validate_bronze.sql

SELECT
    'bronze_documents' AS table_name,
    COUNT(*)           AS total_rows,
    COUNT(DISTINCT doc_id) AS distinct_doc_ids,
    COUNT(DISTINCT record_hash) AS distinct_hashes,
    SUM(CASE WHEN doc_id IS NULL THEN 1 ELSE 0 END) AS null_doc_ids,
    SUM(CASE WHEN raw_text IS NULL OR raw_text = '' THEN 1 ELSE 0 END) AS empty_raw_text,
    SUM(CASE WHEN record_hash IS NULL THEN 1 ELSE 0 END) AS null_hashes,
    MIN(ingested_at) AS earliest_ingest,
    MAX(ingested_at) AS latest_ingest
FROM iceberg.public.bronze_documents;

-- Partition summary
SELECT
    ingest_date,
    COUNT(*) AS doc_count,
    COUNT(DISTINCT loai_van_ban) AS unique_doc_types,
    COUNT(DISTINCT co_quan_ban_hanh) AS unique_authorities
FROM iceberg.public.bronze_documents
GROUP BY ingest_date
ORDER BY ingest_date DESC
LIMIT 30;

-- DLQ check
SELECT
    COUNT(*) AS dlq_total,
    MIN(arrived_at) AS earliest,
    MAX(arrived_at) AS latest
FROM iceberg.public.bronze_dlq;
