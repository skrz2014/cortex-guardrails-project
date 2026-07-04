-- Snowflake infrastructure for BFSI AI Security Operations Center (AISOC)
-- Co-authored with CoCo

-- =============================================================================
-- SETUP
-- =============================================================================
CREATE DATABASE IF NOT EXISTS GUARDRAILS_MONITOR;
CREATE SCHEMA IF NOT EXISTS GUARDRAILS_MONITOR.SECURITY;
USE SCHEMA GUARDRAILS_MONITOR.SECURITY;

-- =============================================================================
-- 1. INCIDENT MANAGEMENT TABLE
--    Stores auto-generated and manually created AI security incidents
-- =============================================================================
CREATE TABLE IF NOT EXISTS GUARDRAILS_MONITOR.SECURITY.AI_INCIDENTS (
    INCIDENT_ID VARCHAR DEFAULT 'AI-' || YEAR(CURRENT_TIMESTAMP()) || '-' || LPAD(SEQ4()::VARCHAR, 6, '0'),
    CREATED_AT TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    SEVERITY VARCHAR,          -- P1, P2, P3
    STATUS VARCHAR DEFAULT 'OPEN',  -- OPEN, INVESTIGATING, RESOLVED, CLOSED
    OWNER VARCHAR DEFAULT 'SOC_TEAM',
    USER_NAME VARCHAR,
    ROLE_NAME VARCHAR,
    AGENTIC_SOURCE VARCHAR,
    REQUEST_ID VARCHAR,
    DESCRIPTION VARCHAR,
    ROOT_CAUSE VARCHAR,
    REMEDIATION VARCHAR,
    CREDITS_IMPACTED FLOAT,
    RESOLVED_AT TIMESTAMP_NTZ,
    RESOLVED_BY VARCHAR,
    AUDIT_HASH VARCHAR
);

-- =============================================================================
-- 2. COMPLIANCE SNAPSHOTS — Long-term retention (5-7 years for BFSI)
-- =============================================================================
CREATE TABLE IF NOT EXISTS GUARDRAILS_MONITOR.SECURITY.COMPLIANCE_SNAPSHOTS (
    SNAPSHOT_ID NUMBER AUTOINCREMENT,
    SNAPSHOT_DATE TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
    REPORT_PERIOD_START DATE,
    REPORT_PERIOD_END DATE,
    TOTAL_SCANS NUMBER,
    TOTAL_FLAGS NUMBER,
    FLAG_RATE_PCT FLOAT,
    RISK_SCORE FLOAT,
    TRUST_SCORE FLOAT,
    PRIVILEGED_FLAGS NUMBER,
    OFF_HOURS_FLAGS NUMBER,
    VELOCITY_ALERTS NUMBER,
    CREDIT_CONSUMPTION FLOAT,
    UNIQUE_USERS NUMBER,
    COMPLIANCE_PASS NUMBER,
    COMPLIANCE_FAIL NUMBER,
    AUDIT_HASH VARCHAR,
    REPORT_TEXT VARCHAR(16777216)
);

-- =============================================================================
-- 3. DYNAMIC TABLE: Hourly aggregated summary (5-min lag)
-- =============================================================================
CREATE OR REPLACE DYNAMIC TABLE GUARDRAILS_MONITOR.SECURITY.GUARDRAIL_HOURLY_SUMMARY
    TARGET_LAG = '5 minutes'
    WAREHOUSE = COMPUTE_WH
AS
SELECT
    DATE_TRUNC('hour', USAGE_TIME) AS SCAN_HOUR,
    AGENTIC_SOURCE,
    METADATA:role_name::VARCHAR AS ROLE_NAME,
    COUNT(*) AS SCAN_COUNT,
    SUM(TOKEN_CREDITS) AS TOTAL_CREDITS,
    SUM(TOKENS) AS TOTAL_TOKENS,
    SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS FLAGGED_COUNT,
    ROUND(FLAGGED_COUNT / NULLIF(SCAN_COUNT, 0) * 100, 2) AS FLAG_RATE_PCT
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -30, CURRENT_TIMESTAMP())
GROUP BY SCAN_HOUR, AGENTIC_SOURCE, ROLE_NAME;

-- =============================================================================
-- 4. DYNAMIC TABLE: User risk scores (10-min refresh)
-- =============================================================================
CREATE OR REPLACE DYNAMIC TABLE GUARDRAILS_MONITOR.SECURITY.USER_RISK_SCORES
    TARGET_LAG = '10 minutes'
    WAREHOUSE = COMPUTE_WH
AS
WITH user_stats AS (
    SELECT
        USER_NAME,
        COUNT(*) AS SCAN_COUNT,
        SUM(TOKEN_CREDITS) AS TOTAL_CREDITS,
        SUM(TOKENS) AS TOTAL_TOKENS,
        SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS FLAGGED_COUNT,
        SUM(CASE WHEN HOUR(USAGE_TIME) < 8 OR HOUR(USAGE_TIME) >= 20 THEN 1 ELSE 0 END) AS OFF_HOURS_COUNT,
        SUM(CASE WHEN DAYOFWEEK(USAGE_TIME) IN (0, 6) THEN 1 ELSE 0 END) AS WEEKEND_COUNT,
        COUNT(DISTINCT METADATA:role_name::VARCHAR) AS UNIQUE_ROLES,
        MAX(USAGE_TIME) AS LAST_SEEN
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
    WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
    GROUP BY USER_NAME
    HAVING SCAN_COUNT >= 3
)
SELECT
    *,
    ROUND(FLAGGED_COUNT / NULLIF(SCAN_COUNT, 0) * 100, 2) AS FLAG_RATE_PCT,
    ROUND(OFF_HOURS_COUNT / NULLIF(SCAN_COUNT, 0) * 100, 2) AS OFF_HOURS_PCT,
    -- Composite risk: 30% flag rate + 25% volume + 20% off-hours + 15% role diversity + 10% weekend
    ROUND(
        LEAST(FLAGGED_COUNT / NULLIF(SCAN_COUNT, 0) * 100, 100) * 0.30
        + LEAST(FLAGGED_COUNT / NULLIF((SELECT MAX(FLAGGED_COUNT) FROM user_stats), 1) * 100, 100) * 0.25
        + LEAST(OFF_HOURS_COUNT / NULLIF(SCAN_COUNT, 0) * 100 * 2, 100) * 0.20
        + LEAST((UNIQUE_ROLES - 1) * 25, 100) * 0.15
        + LEAST(WEEKEND_COUNT / NULLIF(SCAN_COUNT, 0) * 100 * 2, 100) * 0.10
    , 1) AS BEHAVIOR_RISK_SCORE
FROM user_stats;

-- =============================================================================
-- 5. VIEW: Enterprise AI Risk Score (matches Streamlit calculation)
-- =============================================================================
CREATE OR REPLACE VIEW GUARDRAILS_MONITOR.SECURITY.ENTERPRISE_RISK_SCORE AS
WITH base AS (
    SELECT
        COUNT(*) AS total_scans,
        SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS total_flags,
        SUM(TOKEN_CREDITS) AS total_credits,
        SUM(CASE WHEN METADATA:role_name::VARCHAR IN ('ACCOUNTADMIN','SYSADMIN','SECURITYADMIN')
                 AND GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS priv_flags,
        SUM(CASE WHEN (HOUR(USAGE_TIME) < 8 OR HOUR(USAGE_TIME) >= 20)
                 AND GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS off_hours_flags,
        SUM(CASE WHEN PARENT_REQUEST_ID IS NOT NULL AND GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS nested_flags
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
    WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
)
SELECT
    CURRENT_TIMESTAMP() AS COMPUTED_AT,
    total_scans,
    total_flags,
    ROUND(total_flags / NULLIF(total_scans, 0) * 100, 4) AS flag_rate_pct,
    -- 25% injection rate (normalized to 15% threshold)
    LEAST(ROUND(total_flags / NULLIF(total_scans, 0) * 100 / 15 * 100, 1), 100) * 0.25 AS injection_component,
    -- 20% privileged access
    LEAST(priv_flags * 20, 100) * 0.20 AS privileged_component,
    -- 15% off-hours
    LEAST(off_hours_flags * 15, 100) * 0.15 AS offhours_component,
    -- 10% cost (normalized to 1 credit/day budget)
    LEAST(total_credits / 7 / 1.0 * 50, 100) * 0.10 AS cost_component,
    -- 5% nested chains
    LEAST(nested_flags * 25, 100) * 0.05 AS chain_component,
    -- Total risk score
    ROUND(
        LEAST(ROUND(total_flags / NULLIF(total_scans, 0) * 100 / 15 * 100, 1), 100) * 0.25
        + LEAST(priv_flags * 20, 100) * 0.20
        + LEAST(off_hours_flags * 15, 100) * 0.15
        + LEAST(total_credits / 7 / 1.0 * 50, 100) * 0.10
        + LEAST(nested_flags * 25, 100) * 0.05
    , 1) AS ENTERPRISE_RISK_SCORE,
    CASE
        WHEN ENTERPRISE_RISK_SCORE >= 60 THEN 'CRITICAL'
        WHEN ENTERPRISE_RISK_SCORE >= 41 THEN 'HIGH'
        WHEN ENTERPRISE_RISK_SCORE >= 21 THEN 'MODERATE'
        ELSE 'LOW'
    END AS RISK_LEVEL,
    ROUND((1 - total_flags / NULLIF(total_scans, 0)) * 100, 1) AS TRUST_SCORE
FROM base;

-- =============================================================================
-- 6. VIEW: Daily compliance summary (90 days, for board reporting)
-- =============================================================================
CREATE OR REPLACE VIEW GUARDRAILS_MONITOR.SECURITY.DAILY_COMPLIANCE_REPORT AS
SELECT
    DATE_TRUNC('day', USAGE_TIME) AS REPORT_DATE,
    COUNT(*) AS TOTAL_SCANS,
    COUNT(DISTINCT USER_NAME) AS UNIQUE_USERS,
    COUNT(DISTINCT METADATA:role_name::VARCHAR) AS UNIQUE_ROLES,
    SUM(TOKEN_CREDITS) AS DAILY_CREDITS,
    SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS FLAGS,
    ROUND(FLAGS / NULLIF(TOTAL_SCANS, 0) * 100, 4) AS FLAG_RATE,
    SUM(CASE WHEN METADATA:role_name::VARCHAR IN ('ACCOUNTADMIN','SYSADMIN','SECURITYADMIN')
             AND GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS PRIVILEGED_FLAGS,
    SUM(CASE WHEN (HOUR(USAGE_TIME) < 8 OR HOUR(USAGE_TIME) >= 20)
             AND GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END) AS OFF_HOURS_FLAGS,
    -- Compliance status
    IFF(FLAGS = 0 AND PRIVILEGED_FLAGS = 0 AND OFF_HOURS_FLAGS = 0, 'ALL_PASS', 'HAS_VIOLATIONS') AS COMPLIANCE_STATUS
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -90, CURRENT_TIMESTAMP())
GROUP BY REPORT_DATE
ORDER BY REPORT_DATE DESC;

-- =============================================================================
-- 7. VIEW: MITRE ATLAS detection mapping
-- =============================================================================
CREATE OR REPLACE VIEW GUARDRAILS_MONITOR.SECURITY.MITRE_ATLAS_DETECTIONS AS
WITH tool_scans AS (
    SELECT
        gr.value:tool_type::VARCHAR AS tool_type,
        gr.value:indirect_prompt_injection::BOOLEAN AS is_indirect,
        h.USAGE_TIME,
        h.USER_NAME,
        h.GUARDRAILS_SIGNAL
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY h,
        LATERAL FLATTEN(input => h.GUARDRAIL_RESULTS) gr
    WHERE h.USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
)
SELECT
    'AML.T0051' AS TTP_ID,
    'LLM Prompt Injection' AS TECHNIQUE,
    'Critical' AS SEVERITY,
    COUNT(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 END) AS DETECTION_COUNT,
    MAX(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN USAGE_TIME END) AS LAST_DETECTED
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())

UNION ALL

SELECT
    'AML.T0051.001',
    'Indirect Prompt Injection',
    'Critical',
    COUNT(CASE WHEN is_indirect = TRUE THEN 1 END),
    MAX(CASE WHEN is_indirect = TRUE THEN USAGE_TIME END)
FROM tool_scans

UNION ALL

SELECT
    'AML.T0051.002',
    'Tool Output Manipulation',
    'High',
    COUNT(CASE WHEN is_indirect = TRUE AND tool_type IN ('web_search', 'server_mcp') THEN 1 END),
    MAX(CASE WHEN is_indirect = TRUE AND tool_type IN ('web_search', 'server_mcp') THEN USAGE_TIME END)
FROM tool_scans;

-- =============================================================================
-- 8. NOTIFICATION INTEGRATION
-- =============================================================================
-- IMPORTANT: Replace email addresses with your organization's SOC team
CREATE OR REPLACE NOTIFICATION INTEGRATION AISOC_EMAIL_NOTIFY
    TYPE = EMAIL
    ENABLED = TRUE
    ALLOWED_RECIPIENTS = ('soc@yourcompany.com', 'ciso@yourcompany.com');

-- =============================================================================
-- 9. ALERT: Circuit breaker (flag rate > 15% in last hour)
-- =============================================================================
CREATE OR REPLACE ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_CIRCUIT_BREAKER
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '5 MINUTE'
    IF (EXISTS (
        SELECT 1
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
        WHERE USAGE_TIME >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
        HAVING SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END)::FLOAT
               / NULLIF(COUNT(*), 0) * 100 >= 15
    ))
    THEN
        CALL SYSTEM$SEND_EMAIL(
            'AISOC_EMAIL_NOTIFY',
            'soc@yourcompany.com',
            'CRITICAL: AI Guardrails Circuit Breaker — Flag Rate Exceeded 15%',
            'The AI guardrail flag rate has exceeded 15% in the last hour.\n\nAction Required:\n1. Check GUARDRAILS_MONITOR.SECURITY.ENTERPRISE_RISK_SCORE\n2. Review flagged users: SELECT * FROM GUARDRAILS_MONITOR.SECURITY.USER_RISK_SCORES ORDER BY BEHAVIOR_RISK_SCORE DESC LIMIT 10;\n3. Consider disabling AI tools: ALTER ACCOUNT UNSET AI_SETTINGS;'
        );

ALTER ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_CIRCUIT_BREAKER RESUME;

-- =============================================================================
-- 10. ALERT: Privileged role injection (P1 severity)
-- =============================================================================
CREATE OR REPLACE ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_PRIVILEGED_INJECTION
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '5 MINUTE'
    IF (EXISTS (
        SELECT 1
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
        WHERE USAGE_TIME >= DATEADD('minute', -10, CURRENT_TIMESTAMP())
          AND GUARDRAILS_SIGNAL = TRUE
          AND METADATA:role_name::VARCHAR IN ('ACCOUNTADMIN', 'SYSADMIN', 'SECURITYADMIN')
    ))
    THEN
        CALL SYSTEM$SEND_EMAIL(
            'AISOC_EMAIL_NOTIFY',
            'soc@yourcompany.com,ciso@yourcompany.com',
            'P1 INCIDENT: Prompt Injection on Privileged Role',
            'A prompt injection was detected on a privileged role (ACCOUNTADMIN/SYSADMIN/SECURITYADMIN).\n\nThis is a P1 Security Incident.\n\nImmediate Actions:\n1. Verify user identity\n2. Check for unauthorized data access\n3. Consider disabling the user account\n4. Initiate incident response procedure'
        );

ALTER ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_PRIVILEGED_INJECTION RESUME;

-- =============================================================================
-- 11. ALERT: Velocity spike (user > 3x baseline)
-- =============================================================================
CREATE OR REPLACE ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_VELOCITY_SPIKE
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '10 MINUTE'
    IF (EXISTS (
        WITH baselines AS (
            SELECT USER_NAME, AVG(cnt) AS avg_hourly
            FROM (
                SELECT USER_NAME, DATE_TRUNC('hour', USAGE_TIME) AS h, COUNT(*) AS cnt
                FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
                WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP())
                GROUP BY USER_NAME, h
            )
            GROUP BY USER_NAME
        ),
        current_hour AS (
            SELECT USER_NAME, COUNT(*) AS cnt
            FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
            WHERE USAGE_TIME >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
            GROUP BY USER_NAME
        )
        SELECT 1
        FROM current_hour c JOIN baselines b ON c.USER_NAME = b.USER_NAME
        WHERE c.cnt >= b.avg_hourly * 3 AND c.cnt >= 10
    ))
    THEN
        CALL SYSTEM$SEND_EMAIL(
            'AISOC_EMAIL_NOTIFY',
            'soc@yourcompany.com',
            'WARNING: AI Agent Velocity Spike Detected',
            'One or more users exceeded 3x their normal AI agent activity.\nPossible automated attack or compromised account.\n\nCheck: SELECT * FROM GUARDRAILS_MONITOR.SECURITY.USER_RISK_SCORES ORDER BY BEHAVIOR_RISK_SCORE DESC;'
        );

ALTER ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_VELOCITY_SPIKE RESUME;

-- =============================================================================
-- 12. ALERT: Off-hours flagged activity
-- =============================================================================
CREATE OR REPLACE ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_OFF_HOURS
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '15 MINUTE'
    IF (EXISTS (
        SELECT 1
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
        WHERE USAGE_TIME >= DATEADD('minute', -20, CURRENT_TIMESTAMP())
          AND GUARDRAILS_SIGNAL = TRUE
          AND (HOUR(USAGE_TIME) < 8 OR HOUR(USAGE_TIME) >= 20)
    ))
    THEN
        CALL SYSTEM$SEND_EMAIL(
            'AISOC_EMAIL_NOTIFY',
            'soc@yourcompany.com',
            'WARNING: Off-Hours AI Injection Flag',
            'Prompt injection detected outside business hours.\nPossible credential compromise.\n\nInvestigate immediately.'
        );

ALTER ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_OFF_HOURS RESUME;

-- =============================================================================
-- 13. ALERT: Credit budget exceeded
-- =============================================================================
CREATE OR REPLACE ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_CREDIT_BUDGET
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = '60 MINUTE'
    IF (EXISTS (
        SELECT 1
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
        WHERE USAGE_TIME >= DATE_TRUNC('day', CURRENT_TIMESTAMP())
        HAVING SUM(TOKEN_CREDITS) >= 1.0  -- Adjust per org
    ))
    THEN
        CALL SYSTEM$SEND_EMAIL(
            'AISOC_EMAIL_NOTIFY',
            'soc@yourcompany.com',
            'NOTICE: AI Guardrail Daily Credit Budget Exceeded',
            'Daily guardrail credit spend has exceeded budget.\nReview cost allocation and optimize.'
        );

ALTER ALERT GUARDRAILS_MONITOR.SECURITY.ALERT_CREDIT_BUDGET RESUME;

-- =============================================================================
-- 14. TASK: Weekly compliance snapshot
-- =============================================================================
CREATE OR REPLACE TASK GUARDRAILS_MONITOR.SECURITY.TASK_WEEKLY_COMPLIANCE_SNAPSHOT
    WAREHOUSE = COMPUTE_WH
    SCHEDULE = 'USING CRON 0 6 * * MON UTC'
AS
INSERT INTO GUARDRAILS_MONITOR.SECURITY.COMPLIANCE_SNAPSHOTS
    (REPORT_PERIOD_START, REPORT_PERIOD_END, TOTAL_SCANS, TOTAL_FLAGS,
     FLAG_RATE_PCT, PRIVILEGED_FLAGS, OFF_HOURS_FLAGS, CREDIT_CONSUMPTION,
     UNIQUE_USERS, AUDIT_HASH)
SELECT
    DATEADD('day', -7, CURRENT_DATE()),
    CURRENT_DATE(),
    COUNT(*),
    SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END),
    ROUND(SUM(CASE WHEN GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) * 100, 4),
    SUM(CASE WHEN METADATA:role_name::VARCHAR IN ('ACCOUNTADMIN','SYSADMIN','SECURITYADMIN')
             AND GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END),
    SUM(CASE WHEN (HOUR(USAGE_TIME) < 8 OR HOUR(USAGE_TIME) >= 20)
             AND GUARDRAILS_SIGNAL = TRUE THEN 1 ELSE 0 END),
    SUM(TOKEN_CREDITS),
    COUNT(DISTINCT USER_NAME),
    SHA2(ARRAY_TO_STRING(ARRAY_AGG(REQUEST_ID ORDER BY USAGE_TIME), ','), 256)
FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
WHERE USAGE_TIME >= DATEADD('day', -7, CURRENT_TIMESTAMP());

ALTER TASK GUARDRAILS_MONITOR.SECURITY.TASK_WEEKLY_COMPLIANCE_SNAPSHOT RESUME;

-- =============================================================================
-- 15. ROW ACCESS POLICY: Non-admins see only their own data
-- =============================================================================
CREATE OR REPLACE ROW ACCESS POLICY GUARDRAILS_MONITOR.SECURITY.RAP_USER_SCOPE
AS (row_user VARCHAR) RETURNS BOOLEAN ->
    CURRENT_ROLE() IN ('ACCOUNTADMIN', 'SECURITYADMIN', 'SYSADMIN')
    OR row_user = CURRENT_USER();

-- Example application:
-- ALTER DYNAMIC TABLE GUARDRAILS_MONITOR.SECURITY.USER_RISK_SCORES
--   ADD ROW ACCESS POLICY GUARDRAILS_MONITOR.SECURITY.RAP_USER_SCOPE ON (USER_NAME);

-- =============================================================================
-- VERIFICATION
-- =============================================================================
SHOW DYNAMIC TABLES IN SCHEMA GUARDRAILS_MONITOR.SECURITY;
SHOW ALERTS IN SCHEMA GUARDRAILS_MONITOR.SECURITY;
SHOW VIEWS IN SCHEMA GUARDRAILS_MONITOR.SECURITY;
SHOW TASKS IN SCHEMA GUARDRAILS_MONITOR.SECURITY;
SHOW TABLES IN SCHEMA GUARDRAILS_MONITOR.SECURITY;
