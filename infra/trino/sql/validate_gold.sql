-- Validate Gold layer: all 5 tables, business metric sanity checks
-- Run via: docker exec trino trino --catalog iceberg < infra/trino/sql/validate_gold.sql

-- 1. Daily ingestion stats
SELECT
    'gold_daily_stats' AS table_name,
    COUNT(*) AS rows,
    SUM(total_documents) AS total_docs_across_all_days,
    AVG(avg_word_count) AS avg_word_count_all_time,
    AVG(avg_quality_score) AS avg_quality_all_time,
    SUM(CASE WHEN total_documents < 0 THEN 1 ELSE 0 END) AS negative_count_rows
FROM iceberg.public.gold_daily_stats;

-- 2. Top document types
SELECT
    loai_van_ban,
    SUM(document_count) AS total_docs,
    AVG(avg_word_count) AS avg_words
FROM iceberg.public.gold_legal_type_breakdown
GROUP BY loai_van_ban
ORDER BY total_docs DESC
LIMIT 20;

-- 3. Top issuing authorities
SELECT
    co_quan_ban_hanh,
    SUM(document_count) AS total_docs
FROM iceberg.public.gold_issuing_authority
GROUP BY co_quan_ban_hanh
ORDER BY total_docs DESC
LIMIT 20;

-- 4. Legal field distribution
SELECT
    linh_vuc,
    nganh,
    SUM(document_count) AS total_docs,
    AVG(avg_quality_score) AS avg_quality
FROM iceberg.public.gold_legal_field_stats
GROUP BY linh_vuc, nganh
ORDER BY total_docs DESC
LIMIT 30;

-- 5. Effect status overview
SELECT
    effect_status,
    SUM(document_count) AS total_docs,
    ROUND(100.0 * SUM(document_count) / SUM(SUM(document_count)) OVER (), 2) AS pct
FROM iceberg.public.gold_effect_status
GROUP BY effect_status
ORDER BY total_docs DESC;

-- 6. Non-negative assertions
SELECT
    'gold_daily_stats_non_negative' AS check_name,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS failing_rows
FROM iceberg.public.gold_daily_stats
WHERE total_documents < 0 OR quarantined_count < 0

UNION ALL

SELECT
    'gold_legal_type_non_negative' AS check_name,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS failing_rows
FROM iceberg.public.gold_legal_type_breakdown
WHERE document_count < 0

UNION ALL

SELECT
    'gold_issuing_authority_non_negative' AS check_name,
    CASE WHEN COUNT(*) = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
    COUNT(*) AS failing_rows
FROM iceberg.public.gold_issuing_authority
WHERE document_count < 0;
