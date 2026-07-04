-- Cortex AI Guardrails Usage History - Analytical Queries
-- Co-authored with CoCo

-- =============================================================================
-- 1. RECENT GUARDRAIL SCANS (Last 72 Hours)
-- =============================================================================
SELECT *
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('hour', -72, CURRENT_TIMESTAMP())
ORDER BY USAGE_TIME DESC
LIMIT 100;

-- =============================================================================
-- 2. FLAGGED PROMPT INJECTION ATTEMPTS
-- =============================================================================
SELECT
    USER_NAME,
    AGENTIC_SOURCE,
    REQUEST_ID,
    USAGE_TIME,
    TOKENS,
    TOKEN_CREDITS,
    GUARDRAIL_RESULTS
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE GUARDRAILS_SIGNAL = TRUE
  AND USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY USAGE_TIME DESC;

-- =============================================================================
-- 3. CREDIT & TOKEN USAGE BY AGENTIC SOURCE
-- =============================================================================
SELECT
    AGENTIC_SOURCE,
    COUNT(*) AS scan_count,
    SUM(TOKEN_CREDITS) AS total_credits,
    SUM(TOKENS) AS total_tokens,
    AVG(TOKENS) AS avg_tokens_per_scan,
    SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS flagged_count,
    ROUND(flagged_count / scan_count * 100, 2) AS flag_rate_pct
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY AGENTIC_SOURCE
ORDER BY total_credits DESC;

-- =============================================================================
-- 4. TOP USERS BY GUARDRAIL SCAN VOLUME
-- =============================================================================
SELECT
    USER_NAME,
    COUNT(*) AS scan_count,
    SUM(TOKEN_CREDITS) AS total_credits,
    SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS flagged_count
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY USER_NAME
ORDER BY scan_count DESC
LIMIT 20;

-- =============================================================================
-- 5. HOURLY SCAN TREND
-- =============================================================================
SELECT
    DATE_TRUNC('hour', USAGE_TIME) AS scan_hour,
    COUNT(*) AS scan_count,
    SUM(TOKEN_CREDITS) AS hourly_credits,
    SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS flagged_count
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -3, CURRENT_TIMESTAMP())
GROUP BY scan_hour
ORDER BY scan_hour;

-- =============================================================================
-- 6. GRANULAR TOKEN BREAKDOWN (Input vs Output vs Cache)
-- =============================================================================
SELECT
    AGENTIC_SOURCE,
    SUM(TOKENS_GRANULAR:input::NUMBER) AS input_tokens,
    SUM(TOKENS_GRANULAR:output::NUMBER) AS output_tokens,
    SUM(TOKENS_GRANULAR:cache_read_input::NUMBER) AS cache_read_tokens,
    SUM(TOKENS_GRANULAR:cache_write_input::NUMBER) AS cache_write_tokens,
    SUM(CREDITS_GRANULAR:input::NUMBER) AS input_credits,
    SUM(CREDITS_GRANULAR:output::NUMBER) AS output_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY AGENTIC_SOURCE
ORDER BY input_tokens DESC;

-- =============================================================================
-- 7. TOOL TYPE ANALYSIS (Flatten GUARDRAIL_RESULTS array)
-- =============================================================================
SELECT
    gr.value:tool_type::VARCHAR AS tool_type,
    COUNT(*) AS scan_count,
    SUM(CASE WHEN gr.value:indirect_prompt_injection::BOOLEAN = TRUE THEN 1 ELSE 0 END) AS injection_detected,
    AVG(gr.value:token_count::NUMBER) AS avg_token_count
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY h,
    LATERAL FLATTEN(input => h.GUARDRAIL_RESULTS) gr
WHERE h.USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY tool_type
ORDER BY scan_count DESC;

-- =============================================================================
-- 8. ROLE-LEVEL AUDIT (Which roles trigger the most scans)
-- =============================================================================
SELECT
    METADATA:role_name::VARCHAR AS role_name,
    COUNT(*) AS scan_count,
    SUM(TOKEN_CREDITS) AS total_credits,
    SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS flagged_count
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY role_name
ORDER BY scan_count DESC;

-- =============================================================================
-- 9. DAILY SUMMARY REPORT
-- =============================================================================
SELECT
    DATE_TRUNC('day', USAGE_TIME) AS scan_date,
    COUNT(*) AS total_scans,
    COUNT(DISTINCT USER_NAME) AS unique_users,
    SUM(TOKEN_CREDITS) AS daily_credits,
    SUM(TOKENS) AS daily_tokens,
    SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS daily_flagged,
    ROUND(daily_flagged / total_scans * 100, 2) AS daily_flag_rate_pct
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY scan_date
ORDER BY scan_date DESC;

-- =============================================================================
-- 10. PARENT-CHILD REQUEST ANALYSIS (Nested Agent Calls)
-- =============================================================================
SELECT
    PARENT_REQUEST_ID,
    COUNT(*) AS child_scans,
    SUM(TOKEN_CREDITS) AS total_credits,
    ARRAY_AGG(DISTINCT AGENTIC_SOURCE) AS sources_involved,
    MAX(GUARDRAILS_SIGNAL::INT) AS any_flagged
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE PARENT_REQUEST_ID IS NOT NULL
  AND USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY PARENT_REQUEST_ID
HAVING child_scans > 1
ORDER BY child_scans DESC
LIMIT 50;
