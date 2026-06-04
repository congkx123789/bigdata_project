-- Validate Silver layer: quality metrics, quarantine rates, date parsing
-- Run via: docker exec trino trino --catalog iceberg < infra/trino/sql/validate_silver.sql

SELECT
    'silver_documents' AS table_name,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT doc_id) AS distinct_docs,
    AVG(word_count) AS avg_word_count,
    AVG(char_count) AS avg_char_count,
    AVG(quality_score) AS avg_quality_score,
    MIN(quality_score) AS min_quality,
    MAX(quality_score) AS max_quality,
    SUM(CASE WHEN clean_text IS NULL THEN 1 ELSE 0 END) AS null_clean_text,
    SUM(CASE WHEN issuance_date IS NULL THEN 1 ELSE 0 END) AS unparsed_dates
FROM iceberg.public.silver_documents;

-- Quarantine summary
SELECT
    dq_rule,
    COUNT(*) AS quarantined_count,
    MIN(quarantined_at) AS earliest,
    MAX(quarantined_at) AS latest
FROM iceberg.public.silver_quarantine
GROUP BY dq_rule
ORDER BY quarantined_count DESC;

-- Bronze → Silver reconciliation (data drift check)
SELECT
    b.ingest_date,
    b.bronze_count,
    s.silver_count,
    q.quarantine_count,
    b.bronze_count - COALESCE(s.silver_count, 0) - COALESCE(q.quarantine_count, 0) AS unaccounted
FROM (
    SELECT ingest_date, COUNT(*) AS bronze_count
    FROM iceberg.public.bronze_documents
    GROUP BY ingest_date
) b
LEFT JOIN (
    SELECT ingest_date, COUNT(*) AS silver_count
    FROM iceberg.public.silver_documents
    GROUP BY ingest_date
) s ON b.ingest_date = s.ingest_date
LEFT JOIN (
    SELECT DATE(quarantined_at) AS ingest_date, COUNT(*) AS quarantine_count
    FROM iceberg.public.silver_quarantine
    GROUP BY DATE(quarantined_at)
) q ON b.ingest_date = q.ingest_date
ORDER BY b.ingest_date DESC;
