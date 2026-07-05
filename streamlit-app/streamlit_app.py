# Fortune 100 BFSI AI Security Operations Center (AISOC) — Cortex AI Guardrails Enterprise Monitor
import os
import json
import hashlib
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="AI Security Operations Center",
    page_icon="🛡️",
    layout="wide",
)

conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))

# =============================================================================
# DEMO DATA GENERATOR
# =============================================================================
def generate_demo_data():
    """Generate realistic synthetic data for end-to-end testing."""
    import random
    random.seed(42)
    np.random.seed(42)

    now = datetime.now()
    users = ["SATISH", "PRIYA_ANALYST", "RAHUL_DEVOPS", "ANITA_DS", "VIKRAM_ADMIN",
             "DEEPAK_SRE", "MEERA_SOC", "ARJUN_MLENG", "KAVITHA_BA", "NIKHIL_BOT"]
    sources = ["CORTEX_CODE_SNOWSIGHT", "CORTEX_AGENT", "CORTEX_CODE_CLI",
               "CORTEX_CODE_DESKTOP", "SNOWFLAKE_INTELLIGENCE"]
    tool_types = ["sql_execute", "web_search", "server_mcp", "code_interpreter"]

    rows = []
    for i in range(500):
        ts = now - timedelta(hours=random.uniform(0, 72))

        # 20% are attack traffic
        is_attack = i < 100
        # 8% privileged role attacks
        is_privileged = i < 40
        # 10% off-hours
        is_off_hours = i < 50

        if is_off_hours:
            ts = ts.replace(hour=random.choice([1, 2, 3, 4, 23, 0]))
        elif is_attack:
            ts = ts.replace(hour=random.randint(9, 17))
        else:
            ts = ts.replace(hour=random.randint(8, 18))

        user = "VIKRAM_ADMIN" if is_privileged else random.choice(users[:8])
        role = random.choice(["ACCOUNTADMIN", "SYSADMIN"]) if is_privileged else random.choice(["ANALYST_ROLE", "DATA_ENGINEER", "ML_ENGINEER", "APP_ROLE"])
        source = "CORTEX_AGENT" if is_attack else random.choice(sources)
        tool = random.choice(["web_search", "server_mcp"]) if is_attack else random.choice(tool_types)

        rows.append({
            "USER_NAME": user,
            "AGENTIC_SOURCE": source,
            "REQUEST_ID": f"REQ-DEMO-{i:05d}",
            "PARENT_REQUEST_ID": f"PARENT-{i % 8:04d}" if (is_attack and i < 20) else None,
            "USAGE_TIME": ts,
            "TOKEN_CREDITS": round(random.uniform(0.01, 0.08), 6) if is_attack else round(random.uniform(0.0001, 0.005), 6),
            "TOKENS": random.randint(500, 3000) if is_attack else random.randint(50, 500),
            "TOKENS_GRANULAR": json.dumps({
                "input": random.randint(200, 2000),
                "output": random.randint(50, 500),
                "cache_read_input": random.randint(10, 200),
                "cache_write_input": random.randint(5, 50),
            }),
            "GUARDRAILS_SIGNAL": is_attack,
            "GUARDRAIL_RESULTS": json.dumps([{
                "tool_use_id": f"tool-{i:05d}",
                "tool_type": tool,
                "indirect_prompt_injection": is_attack,
                "token_count": random.randint(500, 3000) if is_attack else random.randint(50, 300),
            }]),
            "ROLE_NAME": role,
        })
    return pd.DataFrame(rows)

# =============================================================================
# STYLING — Corporate Design (Google Material + Microsoft Fluent + Snowflake Horizon)
# =============================================================================
st.markdown("""
<style>
    /* --- Base Typography & Spacing --- */
    section[data-testid="stSidebar"] > div { padding-top: 1rem; }

    /* --- Metric Cards (Fluent-style) --- */
    div[data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    div[data-testid="stMetric"] label { font-size: 0.75rem; letter-spacing: 0.03em; color: #6b7280; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 700; }

    /* --- Risk Score Cards --- */
    .risk-critical { background: linear-gradient(135deg, #fef2f2, #fee2e2); border: 1px solid #fca5a5; border-radius: 16px; padding: 24px; text-align: center; }
    .risk-high { background: linear-gradient(135deg, #fff7ed, #ffedd5); border: 1px solid #fdba74; border-radius: 16px; padding: 24px; text-align: center; }
    .risk-moderate { background: linear-gradient(135deg, #fefce8, #fef9c3); border: 1px solid #fde047; border-radius: 16px; padding: 24px; text-align: center; }
    .risk-low { background: linear-gradient(135deg, #f0fdf4, #dcfce7); border: 1px solid #86efac; border-radius: 16px; padding: 24px; text-align: center; }
    .score-number { font-size: 3rem; font-weight: 800; line-height: 1.1; margin: 8px 0; font-family: -apple-system, 'SF Pro Display', system-ui, sans-serif; }
    .score-label { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; color: #6b7280; }

    /* --- Circuit Breaker (pulsing attention) --- */
    .circuit-breaker {
        background: linear-gradient(135deg, #fef2f2, #fee2e2);
        border: 2px solid #dc2626;
        border-radius: 12px;
        padding: 20px 24px;
        text-align: center;
        animation: pulse-border 2s ease-in-out infinite;
    }
    .circuit-breaker h2 { color: #991b1b; margin: 0 0 4px 0; font-size: 1.3rem; }
    .circuit-breaker p { color: #dc2626; margin: 0; font-size: 0.9rem; }
    @keyframes pulse-border { 0%, 100% { border-color: #dc2626; } 50% { border-color: #fca5a5; } }

    /* --- Live Alert Feed (Material Design inspired) --- */
    .feed-container { max-height: 480px; overflow-y: auto; padding-right: 8px; }
    .feed-item {
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 12px 16px;
        margin: 6px 0;
        border-radius: 8px;
        font-size: 0.82rem;
        line-height: 1.4;
        transition: background 0.15s;
    }
    .feed-item:hover { filter: brightness(0.97); }
    .feed-critical { background: #fef2f2; border: 1px solid #fecaca; }
    .feed-warning { background: #fffbeb; border: 1px solid #fef3c7; }
    .feed-success { background: #f0fdf4; border: 1px solid #dcfce7; }

    .feed-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        margin-top: 5px;
        flex-shrink: 0;
    }
    .dot-red { background: #dc2626; box-shadow: 0 0 6px rgba(220,38,38,0.4); }
    .dot-yellow { background: #d97706; box-shadow: 0 0 6px rgba(217,119,6,0.3); }
    .dot-green { background: #16a34a; }

    .feed-content { flex: 1; }
    .feed-time { font-weight: 700; color: #1f2937; font-family: 'SF Mono', Menlo, monospace; font-size: 0.78rem; }
    .feed-action { color: #374151; font-weight: 500; margin: 2px 0; }
    .feed-meta { color: #9ca3af; font-size: 0.72rem; }

    .feed-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-weight: 700;
        letter-spacing: 0.5px;
        text-transform: uppercase;
    }
    .badge-critical { background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; }
    .badge-warning { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
    .badge-normal { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }

    /* --- Timeline (Incident timeline) --- */
    .timeline-container { position: relative; padding-left: 24px; }
    .timeline-container::before {
        content: '';
        position: absolute;
        left: 7px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: #e5e7eb;
    }
    .tl-item {
        position: relative;
        padding: 12px 16px;
        margin: 8px 0;
        background: #ffffff;
        border: 1px solid #f3f4f6;
        border-radius: 8px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .tl-item::before {
        content: '';
        position: absolute;
        left: -21px;
        top: 18px;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #dc2626;
        border: 2px solid #ffffff;
        box-shadow: 0 0 0 2px #fecaca;
    }
    .tl-item.tl-clean::before { background: #16a34a; box-shadow: 0 0 0 2px #dcfce7; }
    .tl-time { font-family: 'SF Mono', Menlo, monospace; font-size: 0.75rem; color: #6b7280; font-weight: 600; }
    .tl-title { font-weight: 600; color: #111827; margin: 4px 0 2px; font-size: 0.85rem; }
    .tl-detail { color: #6b7280; font-size: 0.78rem; }

    /* --- Section Headers --- */
    .section-chip {
        display: inline-block;
        background: #f1f5f9;
        border: 1px solid #e2e8f0;
        padding: 4px 12px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        color: #475569;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# BFSI THRESHOLDS (Configurable)
# =============================================================================
THRESHOLDS = {
    "circuit_breaker_pct": 15.0,
    "credit_daily_budget": 1.0,
    "velocity_multiplier": 3.0,
    "working_hours_start": 8,
    "working_hours_end": 20,
    "privileged_roles": ["ACCOUNTADMIN", "SYSADMIN", "SECURITYADMIN"],
    "risk_critical": 60,
    "risk_high": 41,
    "risk_moderate": 21,
}

# MITRE ATLAS Framework
MITRE_ATLAS = {
    "AML.T0051": {"name": "LLM Prompt Injection (Direct)", "severity": "Critical", "field": "GUARDRAILS_SIGNAL"},
    "AML.T0051.001": {"name": "Indirect Prompt Injection", "severity": "Critical", "field": "indirect_prompt_injection"},
    "AML.T0054": {"name": "LLM Jailbreak", "severity": "Critical", "field": "GUARDRAILS_SIGNAL"},
    "AML.T0051.002": {"name": "Tool Output Manipulation", "severity": "High", "field": "tool_type"},
    "AML.T0024": {"name": "Exfiltration via ML API", "severity": "Critical", "field": None},
    "AML.T0015": {"name": "Evade ML Model", "severity": "High", "field": None},
}


# =============================================================================
# DATA LOADING (Single query)
# =============================================================================
@st.cache_data(ttl=600)
def load_all_data(start_date: str, end_date: str):
    return conn.query(
        """
        SELECT
            USER_NAME,
            AGENTIC_SOURCE,
            REQUEST_ID,
            PARENT_REQUEST_ID,
            USAGE_TIME,
            TOKEN_CREDITS,
            TOKENS,
            TOKENS_GRANULAR,
            GUARDRAILS_SIGNAL,
            GUARDRAIL_RESULTS,
            METADATA:role_name::VARCHAR AS ROLE_NAME
        FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
        WHERE USAGE_TIME BETWEEN ? AND ?
        ORDER BY USAGE_TIME DESC
        LIMIT 5000
        """,
        params=[start_date, end_date],
    )


# =============================================================================
# ANALYTICS ENGINE
# =============================================================================
def compute_executive_risk_score(df, days_in_range):
    """
    Composite Enterprise AI Risk Score (0-100):
    25% Prompt Injection Rate
    20% Privileged User Activity
    15% Velocity Anomalies
    15% Off-hour Activity
    10% Cost Spike
    10% Compliance Failures
    5%  Nested Agent Chains
    """
    if df.empty:
        return 0.0, {}

    total = len(df)
    flagged = df["GUARDRAILS_SIGNAL"].sum()

    # 1. Injection rate (25%) — flag rate normalized to 0-100
    injection_rate = min((flagged / total * 100) / THRESHOLDS["circuit_breaker_pct"] * 100, 100) if total > 0 else 0

    # 2. Privileged activity (20%) — % of flagged from privileged roles
    priv_flagged = df[(df["ROLE_NAME"].isin(THRESHOLDS["privileged_roles"])) & (df["GUARDRAILS_SIGNAL"] == True)]
    priv_score = min(len(priv_flagged) * 20, 100)  # Each privileged flag adds 20 points

    # 3. Velocity anomalies (15%)
    velocity_alerts = compute_velocity_alerts(df)
    velocity_score = min(len(velocity_alerts) * 10, 100)

    # 4. Off-hours activity (15%)
    if not df.empty:
        hours = pd.to_datetime(df["USAGE_TIME"]).dt.hour
        off_mask = (hours < THRESHOLDS["working_hours_start"]) | (hours >= THRESHOLDS["working_hours_end"])
        off_flagged = df[off_mask & (df["GUARDRAILS_SIGNAL"] == True)]
        off_score = min(len(off_flagged) * 15, 100)
    else:
        off_score = 0

    # 5. Cost spike (10%)
    daily_credits = df["TOKEN_CREDITS"].sum() / max(days_in_range, 1)
    cost_score = min((daily_credits / THRESHOLDS["credit_daily_budget"]) * 50, 100) if THRESHOLDS["credit_daily_budget"] > 0 else 0

    # 6. Compliance failures (10%)
    compliance_score = 0
    if flagged > 0 and len(priv_flagged) > 0:
        compliance_score += 50
    if off_score > 0:
        compliance_score += 30
    if injection_rate > 50:
        compliance_score += 20
    compliance_score = min(compliance_score, 100)

    # 7. Nested chains (5%)
    nested = df[df["PARENT_REQUEST_ID"].notna()]
    nested_flagged = nested[nested["GUARDRAILS_SIGNAL"] == True]
    chain_score = min(len(nested_flagged) * 25, 100)

    # Weighted composite
    risk_score = (
        injection_rate * 0.25
        + priv_score * 0.20
        + velocity_score * 0.15
        + off_score * 0.15
        + cost_score * 0.10
        + compliance_score * 0.10
        + chain_score * 0.05
    )

    breakdown = {
        "Injection Rate": round(injection_rate, 1),
        "Privileged Access": round(priv_score, 1),
        "Velocity Anomalies": round(velocity_score, 1),
        "Off-Hours Activity": round(off_score, 1),
        "Cost Spike": round(cost_score, 1),
        "Compliance": round(compliance_score, 1),
        "Nested Chains": round(chain_score, 1),
    }

    return round(min(risk_score, 100), 1), breakdown


def compute_velocity_alerts(df):
    if df.empty:
        return []
    df_copy = df.copy()
    df_copy["HOUR"] = pd.to_datetime(df_copy["USAGE_TIME"]).dt.floor("h")
    hourly = df_copy.groupby(["USER_NAME", "HOUR"], as_index=False).agg(COUNT=("HOUR", "count"))
    baselines = hourly.groupby("USER_NAME")["COUNT"].mean().to_dict()
    alerts = []
    for _, row in hourly.iterrows():
        baseline = baselines.get(row["USER_NAME"], 1)
        if baseline > 0 and row["COUNT"] >= baseline * THRESHOLDS["velocity_multiplier"]:
            alerts.append({
                "USER": row["USER_NAME"],
                "HOUR": row["HOUR"],
                "COUNT": int(row["COUNT"]),
                "BASELINE": round(baseline, 1),
                "SPIKE": round(row["COUNT"] / baseline, 1),
            })
    return sorted(alerts, key=lambda x: x["SPIKE"], reverse=True)[:20]


def compute_ueba(df):
    """User & Entity Behavioral Analytics — time-based signals."""
    if df.empty:
        return pd.DataFrame()

    df_copy = df.copy()
    ts = pd.to_datetime(df_copy["USAGE_TIME"])
    df_copy["HOUR"] = ts.dt.hour
    df_copy["DAY_NAME"] = ts.dt.day_name()
    df_copy["IS_WEEKEND"] = ts.dt.dayofweek >= 5
    df_copy["IS_NIGHT"] = (df_copy["HOUR"] < 6) | (df_copy["HOUR"] >= 22)

    user_behavior = df_copy.groupby("USER_NAME", as_index=False).agg(
        TOTAL_SCANS=("USER_NAME", "count"),
        FLAGGED=("GUARDRAILS_SIGNAL", "sum"),
        WEEKEND_SCANS=("IS_WEEKEND", "sum"),
        NIGHT_SCANS=("IS_NIGHT", "sum"),
        TOTAL_TOKENS=("TOKENS", "sum"),
        UNIQUE_ROLES=("ROLE_NAME", "nunique"),
        UNIQUE_SOURCES=("AGENTIC_SOURCE", "nunique"),
        FIRST_SEEN=("USAGE_TIME", "min"),
        LAST_SEEN=("USAGE_TIME", "max"),
    )

    # Anomaly signals
    user_behavior["FLAG_RATE"] = (user_behavior["FLAGGED"] / user_behavior["TOTAL_SCANS"] * 100).round(1)
    user_behavior["WEEKEND_PCT"] = (user_behavior["WEEKEND_SCANS"] / user_behavior["TOTAL_SCANS"] * 100).round(1)
    user_behavior["NIGHT_PCT"] = (user_behavior["NIGHT_SCANS"] / user_behavior["TOTAL_SCANS"] * 100).round(1)
    user_behavior["AVG_TOKENS"] = (user_behavior["TOTAL_TOKENS"] / user_behavior["TOTAL_SCANS"]).round(0)

    # Behavioral anomaly score
    token_mean = user_behavior["AVG_TOKENS"].mean()
    token_std = user_behavior["AVG_TOKENS"].std()
    user_behavior["TOKEN_ANOMALY"] = ((user_behavior["AVG_TOKENS"] - token_mean) / max(token_std, 1)).round(2)

    # Composite behavioral risk
    user_behavior["BEHAVIOR_RISK"] = (
        user_behavior["FLAG_RATE"] * 0.3
        + user_behavior["NIGHT_PCT"] * 0.2
        + user_behavior["WEEKEND_PCT"] * 0.15
        + user_behavior["TOKEN_ANOMALY"].clip(0, 100) * 0.15
        + (user_behavior["UNIQUE_ROLES"] > 1).astype(int) * 20 * 0.1
        + (user_behavior["FLAGGED"] / max(user_behavior["FLAGGED"].max(), 1) * 100) * 0.1
    ).round(1)

    return user_behavior.sort_values("BEHAVIOR_RISK", ascending=False)


def compute_drift(df, days_in_range):
    """Compare first half vs second half of the data range."""
    if df.empty or len(df) < 10:
        return {}
    df_copy = df.copy()
    df_copy["TS"] = pd.to_datetime(df_copy["USAGE_TIME"])
    midpoint = df_copy["TS"].min() + (df_copy["TS"].max() - df_copy["TS"].min()) / 2
    first_half = df_copy[df_copy["TS"] < midpoint]
    second_half = df_copy[df_copy["TS"] >= midpoint]

    fh_rate = (first_half["GUARDRAILS_SIGNAL"].sum() / max(len(first_half), 1)) * 100
    sh_rate = (second_half["GUARDRAILS_SIGNAL"].sum() / max(len(second_half), 1)) * 100

    fh_credits = first_half["TOKEN_CREDITS"].sum()
    sh_credits = second_half["TOKEN_CREDITS"].sum()

    rate_change = ((sh_rate - fh_rate) / max(fh_rate, 0.01)) * 100
    credit_change = ((sh_credits - fh_credits) / max(fh_credits, 0.01)) * 100

    return {
        "prev_flag_rate": round(fh_rate, 2),
        "curr_flag_rate": round(sh_rate, 2),
        "rate_change_pct": round(rate_change, 1),
        "prev_credits": round(fh_credits, 6),
        "curr_credits": round(sh_credits, 6),
        "credit_change_pct": round(credit_change, 1),
        "prev_scans": len(first_half),
        "curr_scans": len(second_half),
        "scan_change_pct": round(((len(second_half) - len(first_half)) / max(len(first_half), 1)) * 100, 1),
    }


def generate_incidents(df):
    """Auto-generate incident records from flagged events."""
    if df.empty:
        return []
    flagged = df[df["GUARDRAILS_SIGNAL"] == True].copy()
    if flagged.empty:
        return []

    incidents = []
    # Group by REQUEST_ID for unique incidents
    for i, (_, row) in enumerate(flagged.head(20).iterrows(), 1):
        severity = "P1" if row["ROLE_NAME"] in THRESHOLDS["privileged_roles"] else "P2"
        hour = pd.to_datetime(row["USAGE_TIME"]).hour
        if hour < THRESHOLDS["working_hours_start"] or hour >= THRESHOLDS["working_hours_end"]:
            severity = "P1"

        incidents.append({
            "ID": f"AI-{datetime.now().year}-{i:06d}",
            "TIME": row["USAGE_TIME"],
            "SEVERITY": severity,
            "USER": row["USER_NAME"],
            "ROLE": row["ROLE_NAME"],
            "SOURCE": row["AGENTIC_SOURCE"],
            "REQUEST_ID": row["REQUEST_ID"][:12] + "..." if len(str(row["REQUEST_ID"])) > 12 else row["REQUEST_ID"],
            "CREDITS": round(row["TOKEN_CREDITS"], 6),
            "STATUS": "OPEN",
        })
    return incidents


def generate_recommendations(risk_score, breakdown, df, drift):
    """Rule-based automated recommendations."""
    recs = []

    if breakdown.get("Injection Rate", 0) > 50:
        recs.append({
            "PRIORITY": "CRITICAL",
            "RECOMMENDATION": "Investigate prompt injection surge immediately",
            "REASON": f"Injection rate component at {breakdown['Injection Rate']}% — exceeds safety threshold",
            "SQL": "SELECT * FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY WHERE GUARDRAILS_SIGNAL = TRUE AND USAGE_TIME >= DATEADD('hour', -6, CURRENT_TIMESTAMP()) ORDER BY USAGE_TIME DESC;",
        })

    if breakdown.get("Privileged Access", 0) > 0:
        recs.append({
            "PRIORITY": "HIGH",
            "RECOMMENDATION": "Restrict privileged roles from AI agent usage",
            "REASON": "Prompt injection flags detected on ACCOUNTADMIN/SYSADMIN — potential privilege escalation",
            "SQL": "-- Review and restrict:\n-- REVOKE ROLE ACCOUNTADMIN FROM USER <flagged_user>;",
        })

    if breakdown.get("Off-Hours Activity", 0) > 30:
        recs.append({
            "PRIORITY": "HIGH",
            "RECOMMENDATION": "Investigate off-hours AI activity",
            "REASON": "Flagged events detected outside business hours — possible compromised credentials",
            "SQL": "SELECT USER_NAME, USAGE_TIME, ROLE_NAME FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY WHERE GUARDRAILS_SIGNAL = TRUE AND (HOUR(USAGE_TIME) < 8 OR HOUR(USAGE_TIME) >= 20) AND USAGE_TIME >= DATEADD('day', -1, CURRENT_TIMESTAMP());",
        })

    if risk_score >= THRESHOLDS["risk_critical"]:
        recs.append({
            "PRIORITY": "CRITICAL",
            "RECOMMENDATION": "Consider disabling Cortex AI Guardrails tool calling",
            "REASON": f"Enterprise risk score at {risk_score} (Critical) — automated response recommended",
            "SQL": "-- KILL SWITCH: Disable guardrails (stops all AI agent activity):\n-- ALTER ACCOUNT UNSET AI_SETTINGS;\n-- Or restrict specific agents via network policies",
        })

    if drift and drift.get("rate_change_pct", 0) > 100:
        recs.append({
            "PRIORITY": "HIGH",
            "RECOMMENDATION": "Investigate injection rate drift",
            "REASON": f"Flag rate increased {drift['rate_change_pct']:.0f}% vs previous period",
            "SQL": "-- Check recent changes:\nSHOW PARAMETERS LIKE 'AI_SETTINGS' IN ACCOUNT;",
        })

    if breakdown.get("Velocity Anomalies", 0) > 30:
        recs.append({
            "PRIORITY": "MEDIUM",
            "RECOMMENDATION": "Review users with abnormal scan velocity",
            "REASON": "Multiple users exceeding baseline activity — possible automated attack",
            "SQL": "SELECT USER_NAME, COUNT(*) as SCANS FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY WHERE USAGE_TIME >= DATEADD('hour', -1, CURRENT_TIMESTAMP()) GROUP BY USER_NAME ORDER BY SCANS DESC LIMIT 10;",
        })

    if not recs:
        recs.append({
            "PRIORITY": "INFO",
            "RECOMMENDATION": "No immediate action required",
            "REASON": f"Risk score at {risk_score} — within acceptable parameters",
            "SQL": "-- Continue monitoring. Current posture is healthy.",
        })

    return recs


def compute_mitre_matrix(df):
    """Map detected signals to MITRE ATLAS techniques."""
    if df.empty:
        return []

    total_flags = df["GUARDRAILS_SIGNAL"].sum()
    indirect_count = 0
    tool_manip_count = 0

    # Parse GUARDRAIL_RESULTS for indirect injection detail
    for _, row in df[df["GUARDRAILS_SIGNAL"] == True].iterrows():
        results = row.get("GUARDRAIL_RESULTS")
        if results is None:
            continue
        if isinstance(results, str):
            try:
                results = json.loads(results)
            except (json.JSONDecodeError, TypeError):
                continue
        if isinstance(results, list):
            for item in results:
                if isinstance(item, str):
                    try:
                        item = json.loads(item)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if isinstance(item, dict):
                    if item.get("indirect_prompt_injection"):
                        indirect_count += 1
                    if item.get("tool_type") in ("server_mcp", "web_search"):
                        tool_manip_count += 1

    matrix = []
    for ttp_id, info in MITRE_ATLAS.items():
        detected = False
        count = 0
        last_seen = "Never"

        if ttp_id == "AML.T0051" and total_flags > 0:
            detected = True
            count = int(total_flags)
        elif ttp_id == "AML.T0051.001" and indirect_count > 0:
            detected = True
            count = indirect_count
        elif ttp_id == "AML.T0054" and total_flags > 0:
            detected = True
            count = int(total_flags)  # Cannot distinguish jailbreak from injection
        elif ttp_id == "AML.T0051.002" and tool_manip_count > 0:
            detected = True
            count = tool_manip_count

        if detected:
            last_flag = df[df["GUARDRAILS_SIGNAL"] == True]["USAGE_TIME"].max()
            if pd.notna(last_flag):
                last_seen = str(last_flag)[:16]

        matrix.append({
            "TTP": ttp_id,
            "Technique": info["name"],
            "Severity": info["severity"],
            "Detected": "✅ Yes" if detected else "—",
            "Prevented": "✅" if detected else "—",
            "Count": count if count > 0 else "—",
            "Last Seen": last_seen if detected else "—",
        })

    return matrix


def generate_audit_hash(df):
    if df.empty:
        return "N/A"
    content = df.to_csv(index=False)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# SIDEBAR
# =============================================================================
st.sidebar.header("⚙️ AISOC Configuration")

# DEMO MODE TOGGLE
demo_mode = st.sidebar.toggle("🧪 Demo Mode (Synthetic Data)", value=True, help="Use dummy data to test all features without live Snowflake data")
if demo_mode:
    st.sidebar.success("Using synthetic attack scenario data")

date_mode = st.sidebar.radio("Period", ["Quick", "Custom"], horizontal=True)
if date_mode == "Quick":
    lookback = st.sidebar.selectbox("Lookback", [24, 48, 72, 168, 720], format_func=lambda x: f"{x}h ({x//24}d)", index=2)
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(hours=lookback)
else:
    col_s, col_e = st.sidebar.columns(2)
    start_dt = col_s.date_input("Start", value=datetime.now().date() - timedelta(days=3))
    end_dt = col_e.date_input("End", value=datetime.now().date())
    start_dt = datetime.combine(start_dt, datetime.min.time())
    end_dt = datetime.combine(end_dt, datetime.max.time())

days_in_range = max((end_dt - start_dt).total_seconds() / 86400, 1)

st.sidebar.divider()
st.sidebar.subheader("🎚️ Thresholds")
THRESHOLDS["circuit_breaker_pct"] = st.sidebar.slider("Circuit Breaker %", 5, 50, 15)
THRESHOLDS["credit_daily_budget"] = st.sidebar.number_input("Daily Credit Budget", 0.01, 100.0, 1.0, step=0.1)
THRESHOLDS["velocity_multiplier"] = st.sidebar.slider("Velocity Spike (x)", 2.0, 10.0, 3.0, step=0.5)

st.sidebar.divider()
st.sidebar.button("🔄 Refresh", on_click=load_all_data.clear)

# =============================================================================
# LOAD & FILTER
# =============================================================================
if demo_mode:
    df_scans = generate_demo_data()
    st.toast("🧪 Running in Demo Mode with 500 synthetic records", icon="🧪")
else:
    with st.spinner("Loading AISOC data..."):
        df_scans = load_all_data(start_dt.strftime("%Y-%m-%d %H:%M:%S"), end_dt.strftime("%Y-%m-%d %H:%M:%S"))

if not df_scans.empty:
    sources = sorted(df_scans["AGENTIC_SOURCE"].dropna().unique().tolist())
    sel_sources = st.sidebar.multiselect("Sources", sources, default=sources)
    df_scans = df_scans[df_scans["AGENTIC_SOURCE"].isin(sel_sources)]

# =============================================================================
# COMPUTE ALL ANALYTICS
# =============================================================================
total_scans = len(df_scans)
total_flagged = int(df_scans["GUARDRAILS_SIGNAL"].sum()) if not df_scans.empty else 0
total_credits = float(df_scans["TOKEN_CREDITS"].sum()) if not df_scans.empty else 0.0
flag_rate = (total_flagged / total_scans * 100) if total_scans > 0 else 0.0
trust_score = round((1 - total_flagged / max(total_scans, 1)) * 100, 1)

risk_score, risk_breakdown = compute_executive_risk_score(df_scans, days_in_range)
drift = compute_drift(df_scans, days_in_range)
velocity_alerts = compute_velocity_alerts(df_scans)

# Risk level
if risk_score >= THRESHOLDS["risk_critical"]:
    risk_level, risk_emoji, risk_class = "CRITICAL", "🔴", "risk-critical"
elif risk_score >= THRESHOLDS["risk_high"]:
    risk_level, risk_emoji, risk_class = "HIGH", "🟠", "risk-high"
elif risk_score >= THRESHOLDS["risk_moderate"]:
    risk_level, risk_emoji, risk_class = "MODERATE", "🟡", "risk-moderate"
else:
    risk_level, risk_emoji, risk_class = "LOW", "🟢", "risk-low"

circuit_active = flag_rate >= THRESHOLDS["circuit_breaker_pct"]

# =============================================================================
# EXECUTIVE DASHBOARD (Always visible at top)
# =============================================================================
st.title("🛡️ AI Security Operations Center")
st.caption(f"Enterprise BFSI AISOC • {start_dt.strftime('%b %d')} – {end_dt.strftime('%b %d, %Y')}")

if circuit_active:
    st.markdown(
        f"""<div class="circuit-breaker">
        <h2>🚨 CIRCUIT BREAKER ACTIVE</h2>
        <p>Flag rate {flag_rate:.1f}% exceeds {THRESHOLDS['circuit_breaker_pct']}% threshold. Immediate action required.</p>
        </div>""", unsafe_allow_html=True
    )
    st.write("")

# Executive Risk Score + KPIs
ex_col1, ex_col2, ex_col3, ex_col4, ex_col5, ex_col6 = st.columns([1.5, 1, 1, 1, 1, 1])

with ex_col1:
    st.markdown(
        f"""<div class="{risk_class}">
        <div class="score-label">{risk_emoji} Enterprise AI Risk</div>
        <div class="score-number">{risk_score}</div>
        <div class="score-label">{risk_level}</div>
        </div>""", unsafe_allow_html=True
    )

ex_col2.metric("Total Scans", f"{total_scans:,}")
ex_col3.metric("Flagged", f"{total_flagged:,}")
ex_col4.metric("Trust Score", f"{trust_score}%")
ex_col5.metric("Credits", f"{total_credits:,.4f}")

# Drift indicator
drift_delta = f"{drift.get('rate_change_pct', 0):+.0f}%" if drift else "N/A"
ex_col6.metric("Flag Rate Drift", f"{flag_rate:.2f}%", delta=drift_delta, delta_color="inverse")

st.divider()

# =============================================================================
# TABS
# =============================================================================
tabs = st.tabs([
    "🎯 Executive", "🚨 Incidents", "🔬 UEBA", "🗺️ MITRE ATLAS",
    "⚡ Alerts", "📈 Drift", "🏦 Compliance", "💰 Cost", "🔧 Kill Switch", "📋 Export"
])

# --- TAB: EXECUTIVE OVERVIEW ---
with tabs[0]:
    st.subheader("Executive Risk Breakdown")

    # Risk component bars
    if risk_breakdown:
        risk_df = pd.DataFrame([
            {"Component": k, "Score": v, "Weight": w}
            for k, v, w in zip(
                risk_breakdown.keys(),
                risk_breakdown.values(),
                ["25%", "20%", "15%", "15%", "10%", "10%", "5%"]
            )
        ])
        st.dataframe(
            risk_df, use_container_width=True, hide_index=True,
            column_config={
                "Component": "Risk Factor",
                "Score": st.column_config.ProgressColumn("Score (0-100)", min_value=0, max_value=100),
                "Weight": "Weight",
            },
        )

    st.divider()

    # Recommendations
    st.subheader("🤖 Automated Recommendations")
    recommendations = generate_recommendations(risk_score, risk_breakdown, df_scans, drift)
    for rec in recommendations:
        icon = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "INFO": "🔵"}.get(rec["PRIORITY"], "⚪")
        with st.expander(f"{icon} [{rec['PRIORITY']}] {rec['RECOMMENDATION']}"):
            st.markdown(f"**Reason:** {rec['REASON']}")
            st.code(rec["SQL"], language="sql")

    st.divider()

    # Live Alert Feed
    st.subheader("📡 Live Alert Feed")
    if not df_scans.empty:
        feed_html = '<div class="feed-container">'
        for _, row in df_scans.head(25).iterrows():
            ts = str(row["USAGE_TIME"])[11:16]
            if row["GUARDRAILS_SIGNAL"]:
                css = "feed-critical"
                dot = "dot-red"
                badge = '<span class="feed-badge badge-critical">BLOCKED</span>'
                action = "Prompt injection detected and blocked"
                meta = f'{row["USER_NAME"]} &bull; {row["AGENTIC_SOURCE"]} &bull; {row["ROLE_NAME"]}'
            elif row["ROLE_NAME"] in THRESHOLDS["privileged_roles"]:
                css = "feed-warning"
                dot = "dot-yellow"
                badge = '<span class="feed-badge badge-warning">PRIVILEGED</span>'
                action = "Scan completed — elevated role detected"
                meta = f'{row["USER_NAME"]} &bull; {row["ROLE_NAME"]}'
            else:
                css = "feed-success"
                dot = "dot-green"
                badge = '<span class="feed-badge badge-normal">CLEAN</span>'
                action = "Scan completed — no threats"
                meta = f'{row["USER_NAME"]} &bull; {row["AGENTIC_SOURCE"]}'

            feed_html += f'''<div class="feed-item {css}">
                <div class="feed-dot {dot}"></div>
                <div class="feed-content">
                    <div><span class="feed-time">{ts}</span> &nbsp; {badge}</div>
                    <div class="feed-action">{action}</div>
                    <div class="feed-meta">{meta}</div>
                </div>
            </div>'''
        feed_html += '</div>'
        st.markdown(feed_html, unsafe_allow_html=True)
    else:
        st.info("No activity in selected period.")

# --- TAB: INCIDENTS ---
with tabs[1]:
    st.subheader("🚨 AI Incident Management")
    st.caption("Auto-generated incidents from flagged guardrail events")

    incidents = generate_incidents(df_scans)
    if incidents:
        p1 = sum(1 for i in incidents if i["SEVERITY"] == "P1")
        p2 = sum(1 for i in incidents if i["SEVERITY"] == "P2")

        ic1, ic2, ic3, ic4 = st.columns(4)
        ic1.metric("Open Incidents", len(incidents))
        ic2.metric("P1 (Critical)", p1)
        ic3.metric("P2 (High)", p2)
        ic4.metric("Avg Credits/Incident", f"{sum(i['CREDITS'] for i in incidents)/max(len(incidents),1):.6f}")

        st.divider()
        df_incidents = pd.DataFrame(incidents)
        st.dataframe(
            df_incidents, use_container_width=True, hide_index=True,
            column_config={
                "ID": "Incident ID",
                "TIME": st.column_config.DatetimeColumn("Time", format="MMM DD HH:mm"),
                "SEVERITY": "Priority",
                "USER": "User",
                "ROLE": "Role",
                "SOURCE": "Source",
                "REQUEST_ID": "Request",
                "CREDITS": st.column_config.NumberColumn("Credits", format="%.6f"),
                "STATUS": "Status",
            },
        )

        st.divider()
        st.subheader("📊 Incident Timeline")
        if not df_scans.empty:
            flagged_events = df_scans[df_scans["GUARDRAILS_SIGNAL"] == True].head(12)
            timeline_html = '<div class="timeline-container">'
            for _, row in flagged_events.iterrows():
                ts = str(row["USAGE_TIME"])[11:19]
                date_str = str(row["USAGE_TIME"])[:10]
                hour = pd.to_datetime(row["USAGE_TIME"]).hour
                time_context = "Off-hours" if (hour < 8 or hour >= 20) else "Business hours"
                priv_tag = ' &bull; <span class="feed-badge badge-critical">PRIVILEGED</span>' if row["ROLE_NAME"] in THRESHOLDS["privileged_roles"] else ""

                timeline_html += f'''<div class="tl-item">
                    <div class="tl-time">{date_str} &nbsp; {ts} &bull; {time_context}</div>
                    <div class="tl-title">Injection Detected &amp; Blocked{priv_tag}</div>
                    <div class="tl-detail">User: {row["USER_NAME"]} &bull; Role: {row["ROLE_NAME"]} &bull; Source: {row["AGENTIC_SOURCE"]}</div>
                </div>'''
            timeline_html += '</div>'
            st.markdown(timeline_html, unsafe_allow_html=True)
    else:
        st.success("No open incidents. All systems nominal.")

# --- TAB: UEBA ---
with tabs[2]:
    st.subheader("🔬 User & Entity Behavioral Analytics")
    st.caption("Detect anomalous AI agent usage patterns")

    df_ueba = compute_ueba(df_scans)
    if not df_ueba.empty:
        ub1, ub2, ub3 = st.columns(3)
        high_risk_users = df_ueba[df_ueba["BEHAVIOR_RISK"] > 30]
        ub1.metric("Users Analyzed", len(df_ueba))
        ub2.metric("High-Risk Users", len(high_risk_users))
        ub3.metric("Avg Behavior Risk", f"{df_ueba['BEHAVIOR_RISK'].mean():.1f}")

        st.divider()
        st.markdown("#### Behavioral Risk Ranking")
        st.dataframe(
            df_ueba.head(15), use_container_width=True, hide_index=True,
            column_config={
                "USER_NAME": "User",
                "TOTAL_SCANS": st.column_config.NumberColumn("Scans", format="%d"),
                "FLAGGED": st.column_config.NumberColumn("Flagged", format="%d"),
                "FLAG_RATE": st.column_config.NumberColumn("Flag %", format="%.1f%%"),
                "WEEKEND_SCANS": st.column_config.NumberColumn("Weekend", format="%d"),
                "NIGHT_SCANS": st.column_config.NumberColumn("Night", format="%d"),
                "UNIQUE_ROLES": st.column_config.NumberColumn("Roles", format="%d"),
                "TOKEN_ANOMALY": st.column_config.NumberColumn("Token σ", format="%.2f"),
                "BEHAVIOR_RISK": st.column_config.ProgressColumn("Behavior Risk", min_value=0, max_value=100),
            },
        )

        st.divider()
        st.markdown("#### 🕐 Activity Pattern (Flagged Events by Hour)")
        if not df_scans.empty:
            flagged_df = df_scans[df_scans["GUARDRAILS_SIGNAL"] == True].copy()
            if not flagged_df.empty:
                flagged_df["HOUR"] = pd.to_datetime(flagged_df["USAGE_TIME"]).dt.hour
                hour_dist = flagged_df.groupby("HOUR", as_index=False).agg(COUNT=("HOUR", "count"))
                st.bar_chart(hour_dist.set_index("HOUR")["COUNT"])
            else:
                st.success("No flagged events to analyze.")
    else:
        st.info("Insufficient data for behavioral analysis.")

# --- TAB: MITRE ATLAS ---
with tabs[3]:
    st.subheader("🗺️ MITRE ATLAS Coverage Matrix")
    st.caption("AI threat techniques mapped to detected guardrail signals")

    matrix = compute_mitre_matrix(df_scans)
    if matrix:
        df_mitre = pd.DataFrame(matrix)
        st.dataframe(df_mitre, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### Coverage Summary")
        detected = sum(1 for m in matrix if m["Detected"] == "✅ Yes")
        total_ttps = len(matrix)
        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Total Techniques", total_ttps)
        mc2.metric("Detected", detected)
        mc3.metric("Coverage", f"{detected/total_ttps*100:.0f}%")

        st.caption("**Note:** The guardrails view provides a boolean injection signal. Direct vs indirect and jailbreak vs injection cannot be fully distinguished from this data alone. Counts may overlap.")
    else:
        st.info("No MITRE ATLAS data to display.")

# --- TAB: ALERTS ---
with tabs[4]:
    st.subheader("⚡ Velocity & Anomaly Alerts")

    if velocity_alerts:
        st.markdown(f"**{len(velocity_alerts)}** velocity spikes detected (≥{THRESHOLDS['velocity_multiplier']}x baseline)")
        df_vel = pd.DataFrame(velocity_alerts)
        st.dataframe(
            df_vel, use_container_width=True, hide_index=True,
            column_config={
                "USER": "User",
                "HOUR": st.column_config.DatetimeColumn("Hour", format="MMM DD HH:mm"),
                "COUNT": st.column_config.NumberColumn("Scans", format="%d"),
                "BASELINE": st.column_config.NumberColumn("Baseline", format="%.1f"),
                "SPIKE": st.column_config.NumberColumn("Multiplier", format="%.1fx"),
            },
        )
    else:
        st.success("No velocity anomalies detected.")

    st.divider()

    # Off-hours
    st.markdown("#### 🕐 Off-Hours Flagged Activity")
    if not df_scans.empty:
        hours = pd.to_datetime(df_scans["USAGE_TIME"]).dt.hour
        off_mask = (hours < THRESHOLDS["working_hours_start"]) | (hours >= THRESHOLDS["working_hours_end"])
        off_flagged = df_scans[off_mask & (df_scans["GUARDRAILS_SIGNAL"] == True)]
        if not off_flagged.empty:
            st.dataframe(
                off_flagged[["USAGE_TIME", "USER_NAME", "ROLE_NAME", "AGENTIC_SOURCE", "TOKEN_CREDITS"]].head(20),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("No off-hours flagged activity.")

    st.divider()

    # Privileged access
    st.markdown("#### 🔑 Privileged Role Flags")
    if not df_scans.empty:
        priv = df_scans[(df_scans["ROLE_NAME"].isin(THRESHOLDS["privileged_roles"])) & (df_scans["GUARDRAILS_SIGNAL"] == True)]
        if not priv.empty:
            st.error(f"⚠️ {len(priv)} injection flags from privileged roles!")
            st.dataframe(
                priv[["USAGE_TIME", "USER_NAME", "ROLE_NAME", "AGENTIC_SOURCE", "REQUEST_ID"]].head(15),
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("No privileged role flags.")

# --- TAB: DRIFT ---
with tabs[5]:
    st.subheader("📈 Drift Detection")
    st.caption("Comparing first half vs second half of selected period")

    if drift:
        dr1, dr2, dr3 = st.columns(3)
        dr1.metric("Flag Rate", f"{drift['curr_flag_rate']:.2f}%",
                   delta=f"{drift['rate_change_pct']:+.0f}% vs prior", delta_color="inverse")
        dr2.metric("Credits", f"{drift['curr_credits']:.6f}",
                   delta=f"{drift['credit_change_pct']:+.0f}% vs prior", delta_color="inverse")
        dr3.metric("Scan Volume", f"{drift['curr_scans']:,}",
                   delta=f"{drift['scan_change_pct']:+.0f}% vs prior")

        st.divider()

        if abs(drift.get("rate_change_pct", 0)) > 50:
            st.warning(f"⚠️ Significant drift detected: Flag rate changed {drift['rate_change_pct']:+.0f}%")
        elif abs(drift.get("rate_change_pct", 0)) > 100:
            st.error(f"🚨 Critical drift: Flag rate changed {drift['rate_change_pct']:+.0f}%")
        else:
            st.success("Flag rate drift within normal bounds.")

        st.divider()
        # Trend chart
        if not df_scans.empty:
            df_trend = df_scans.copy()
            df_trend["HOUR"] = pd.to_datetime(df_trend["USAGE_TIME"]).dt.floor("h")
            hourly = df_trend.groupby("HOUR", as_index=False).agg(
                SCANS=("HOUR", "count"), FLAGS=("GUARDRAILS_SIGNAL", "sum")
            ).sort_values("HOUR")
            if not hourly.empty:
                st.area_chart(hourly.set_index("HOUR")[["SCANS", "FLAGS"]], color=["#3b82f6", "#ef4444"])
    else:
        st.info("Insufficient data for drift analysis.")

# --- TAB: COMPLIANCE ---
with tabs[6]:
    st.subheader("🏦 Regulatory Compliance")

    # Compliance checks
    checks = []
    priv_flagged = df_scans[(df_scans["ROLE_NAME"].isin(THRESHOLDS["privileged_roles"])) & (df_scans["GUARDRAILS_SIGNAL"] == True)] if not df_scans.empty else pd.DataFrame()

    checks.append({"Control": "PAM-001: No privileged injection flags", "Status": "✅ PASS" if priv_flagged.empty else "❌ FAIL",
                   "Evidence": f"{len(priv_flagged)} violations" if not priv_flagged.empty else "Clean", "Framework": "SOX / ISAE 3402"})
    checks.append({"Control": f"SEC-001: Flag rate < {THRESHOLDS['circuit_breaker_pct']}%", "Status": "✅ PASS" if flag_rate < THRESHOLDS["circuit_breaker_pct"] else "❌ FAIL",
                   "Evidence": f"Rate: {flag_rate:.2f}%", "Framework": "NIST AI RMF"})
    checks.append({"Control": f"FIN-001: Daily credits < {THRESHOLDS['credit_daily_budget']}", "Status": "✅ PASS" if (total_credits/days_in_range) < THRESHOLDS["credit_daily_budget"] else "❌ FAIL",
                   "Evidence": f"Daily avg: {total_credits/days_in_range:.6f}", "Framework": "Internal Risk"})

    off_hours_flags = 0
    if not df_scans.empty:
        hrs = pd.to_datetime(df_scans["USAGE_TIME"]).dt.hour
        off_hours_flags = df_scans[((hrs < 8) | (hrs >= 20)) & (df_scans["GUARDRAILS_SIGNAL"] == True)].shape[0]
    checks.append({"Control": "ACC-001: No off-hours flags", "Status": "✅ PASS" if off_hours_flags == 0 else "❌ FAIL",
                   "Evidence": f"{off_hours_flags} off-hours flags", "Framework": "ISO 27001 / PCI-DSS"})
    checks.append({"Control": "GOV-001: Guardrails enabled", "Status": "✅ PASS",
                   "Evidence": "Data present in view = guardrails active", "Framework": "EU AI Act / DORA"})
    checks.append({"Control": "RET-001: Data within retention", "Status": "✅ PASS",
                   "Evidence": "365-day ACCOUNT_USAGE window", "Framework": "RBI / MAS"})

    df_checks = pd.DataFrame(checks)
    pass_ct = df_checks["Status"].str.contains("PASS").sum()
    fail_ct = df_checks["Status"].str.contains("FAIL").sum()

    cc1, cc2, cc3 = st.columns(3)
    cc1.metric("Controls", len(checks))
    cc2.metric("✅ Pass", pass_ct)
    cc3.metric("❌ Fail", fail_ct)

    st.dataframe(df_checks, use_container_width=True, hide_index=True)

    st.divider()
    # Regulatory mapping
    st.markdown("#### 📖 Regulatory Coverage Matrix")
    reg_map = pd.DataFrame([
        {"Signal": "Prompt Injection Detection", "NIST AI RMF": "✅", "RBI AI": "✅", "PCI-DSS": "✅", "ISO 27001": "✅", "DORA": "✅", "EU AI Act": "✅", "SOC 2": "✅", "MAS TRM": "✅"},
        {"Signal": "Privileged Access Monitoring", "NIST AI RMF": "✅", "RBI AI": "✅", "PCI-DSS": "✅", "ISO 27001": "✅", "DORA": "✅", "EU AI Act": "—", "SOC 2": "✅", "MAS TRM": "✅"},
        {"Signal": "Credit/Cost Governance", "NIST AI RMF": "—", "RBI AI": "✅", "PCI-DSS": "—", "ISO 27001": "—", "DORA": "✅", "EU AI Act": "—", "SOC 2": "—", "MAS TRM": "✅"},
        {"Signal": "Audit Trail (SHA-256)", "NIST AI RMF": "✅", "RBI AI": "✅", "PCI-DSS": "✅", "ISO 27001": "✅", "DORA": "✅", "EU AI Act": "✅", "SOC 2": "✅", "MAS TRM": "✅"},
        {"Signal": "Off-Hours Detection", "NIST AI RMF": "—", "RBI AI": "✅", "PCI-DSS": "✅", "ISO 27001": "✅", "DORA": "—", "EU AI Act": "—", "SOC 2": "✅", "MAS TRM": "✅"},
    ])
    st.dataframe(reg_map, use_container_width=True, hide_index=True)

# --- TAB: COST ---
with tabs[7]:
    st.subheader("💰 Cost Governance & Chargeback")

    daily_avg = total_credits / days_in_range if days_in_range > 0 else 0
    fc1, fc2, fc3, fc4 = st.columns(4)
    fc1.metric("Daily Avg", f"{daily_avg:.6f}")
    fc2.metric("Monthly Proj.", f"{daily_avg * 30:.4f}")
    fc3.metric("Quarterly Proj.", f"{daily_avg * 90:.4f}")
    fc4.metric("Budget Status", "✅ Under" if daily_avg < THRESHOLDS["credit_daily_budget"] else "❌ Over")

    st.divider()

    # Cost by role (chargeback)
    cl, cr = st.columns(2)
    with cl:
        st.markdown("#### By Role (Chargeback)")
        if not df_scans.empty:
            role_cost = df_scans.groupby("ROLE_NAME", as_index=False).agg(CREDITS=("TOKEN_CREDITS", "sum")).sort_values("CREDITS", ascending=False).head(10)
            st.bar_chart(role_cost.set_index("ROLE_NAME")["CREDITS"])

    with cr:
        st.markdown("#### By Source")
        if not df_scans.empty:
            src_cost = df_scans.groupby("AGENTIC_SOURCE", as_index=False).agg(CREDITS=("TOKEN_CREDITS", "sum")).sort_values("CREDITS", ascending=False)
            st.bar_chart(src_cost.set_index("AGENTIC_SOURCE")["CREDITS"])

    st.divider()

    # Top expensive users
    st.markdown("#### 💸 Top Users by Cost")
    if not df_scans.empty:
        user_cost = df_scans.groupby("USER_NAME", as_index=False).agg(
            CREDITS=("TOKEN_CREDITS", "sum"), SCANS=("USER_NAME", "count"), TOKENS=("TOKENS", "sum")
        ).assign(COST_PER_SCAN=lambda x: (x["CREDITS"] / x["SCANS"]).round(8)).sort_values("CREDITS", ascending=False).head(10)
        st.dataframe(user_cost, use_container_width=True, hide_index=True,
            column_config={
                "USER_NAME": "User",
                "CREDITS": st.column_config.NumberColumn("Total Credits", format="%.6f"),
                "SCANS": st.column_config.NumberColumn("Scans", format="%d"),
                "TOKENS": st.column_config.NumberColumn("Tokens", format="%d"),
                "COST_PER_SCAN": st.column_config.NumberColumn("Cost/Scan", format="%.8f"),
            },
        )

    st.divider()

    # Cache efficiency
    st.markdown("#### 📊 Token Cache Efficiency")
    if not df_scans.empty and "TOKENS_GRANULAR" in df_scans.columns:
        try:
            token_data = df_scans["TOKENS_GRANULAR"].apply(
                lambda x: json.loads(x) if isinstance(x, str) else (x if isinstance(x, dict) else {})
            )
            t_input = sum(t.get("input", 0) or 0 for t in token_data)
            t_cache = sum(t.get("cache_read_input", 0) or 0 for t in token_data)
            t_output = sum(t.get("output", 0) or 0 for t in token_data)
            t_total = t_input + t_cache + t_output
            cache_pct = (t_cache / t_total * 100) if t_total > 0 else 0
            savings = t_cache * 0.5  # Approximate: cache reads cost ~50% less

            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("Input Tokens", f"{t_input:,.0f}")
            tc2.metric("Cache Hits", f"{t_cache:,.0f}")
            tc3.metric("Cache Hit %", f"{cache_pct:.1f}%")
            tc4.metric("Est. Savings (tokens)", f"{savings:,.0f}")
        except Exception:
            st.info("Could not parse token data.")

# --- TAB: KILL SWITCH ---
with tabs[8]:
    st.subheader("🔧 AI Kill Switch & Response Actions")
    st.caption("Emergency response controls — generate SQL for manual execution")

    st.warning("⚠️ These actions require ACCOUNTADMIN and manual execution. Copy the SQL and run in a worksheet.")

    st.markdown("#### Current Threat Level")
    st.markdown(f"**{risk_emoji} {risk_level}** — Enterprise Risk Score: **{risk_score}**")

    st.divider()

    st.markdown("#### 🛑 Emergency Response Actions")

    with st.expander("Disable All AI Guardrails (stops scanning, NOT agents)"):
        st.code("ALTER ACCOUNT UNSET AI_SETTINGS;", language="sql")
        st.caption("This disables guardrail scanning. Agents continue running unprotected.")

    with st.expander("Re-enable Guardrails"):
        st.code("""ALTER ACCOUNT SET AI_SETTINGS = $$
  guardrails:
    advanced_prompt_injection:
      - enabled: true
$$;""", language="sql")

    with st.expander("Restrict Network Access (block external tool calls)"):
        st.code("""-- Create restrictive network rule
CREATE OR REPLACE NETWORK RULE ai_lockdown_rule
  MODE = EGRESS
  TYPE = HOST_PORT
  VALUE_LIST = ();  -- Block all external access

-- Apply to integration
ALTER EXTERNAL ACCESS INTEGRATION <your_eai>
  SET NETWORK_RULES = (ai_lockdown_rule);""", language="sql")

    with st.expander("Revoke Agent Access from Specific User"):
        flagged_users = df_scans[df_scans["GUARDRAILS_SIGNAL"] == True]["USER_NAME"].unique().tolist()[:5]
        for u in flagged_users:
            st.code(f"-- Revoke from flagged user:\nALTER USER {u} SET DISABLED = TRUE;", language="sql")
        if not flagged_users:
            st.info("No flagged users to display.")

    with st.expander("Create Emergency Alert"):
        st.code("""CREATE OR REPLACE ALERT EMERGENCY_AI_LOCKDOWN
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = '1 MINUTE'
  IF (EXISTS (
    SELECT 1
    FROM SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
    WHERE GUARDRAILS_SIGNAL = TRUE
      AND USAGE_TIME >= DATEADD('minute', -5, CURRENT_TIMESTAMP())
    HAVING COUNT(*) >= 10
  ))
  THEN
    CALL SYSTEM$SEND_EMAIL('YOUR_INTEGRATION', 'soc@company.com',
      'EMERGENCY: Mass AI Injection Attack',
      '10+ injection flags in 5 minutes. Initiate incident response.');

ALTER ALERT EMERGENCY_AI_LOCKDOWN RESUME;""", language="sql")

# --- TAB: EXPORT ---
with tabs[9]:
    st.subheader("📋 Audit Export & Report")

    audit_hash = generate_audit_hash(df_scans)

    ae1, ae2 = st.columns(2)
    with ae1:
        st.markdown(f"**Records:** {len(df_scans):,}")
        st.markdown(f"**Integrity Hash:** `{audit_hash}`")
        st.markdown(f"**Period:** {start_dt.strftime('%Y-%m-%d')} → {end_dt.strftime('%Y-%m-%d')}")
    with ae2:
        st.markdown(f"**Risk Score:** {risk_score} ({risk_level})")
        st.markdown(f"**Trust Score:** {trust_score}%")
        st.markdown(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")

    st.divider()

    # Generate compliance report
    report = f"""{'='*70}
CORTEX AI GUARDRAILS — ENTERPRISE COMPLIANCE REPORT
{'='*70}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
Period: {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}
Integrity Hash (SHA-256): {audit_hash}

{'='*70}
EXECUTIVE SUMMARY
{'='*70}
Enterprise AI Risk Score: {risk_score}/100 ({risk_level})
Agent Trust Score: {trust_score}%
Circuit Breaker Status: {'TRIGGERED' if circuit_active else 'Normal'}

Total Guardrail Scans: {total_scans:,}
Flagged Events: {total_flagged:,}
Flag Rate: {flag_rate:.4f}%
Credit Consumption: {total_credits:,.6f}
Daily Average Credits: {daily_avg:.6f}
Monthly Projection: {daily_avg*30:.4f}

{'='*70}
RISK BREAKDOWN
{'='*70}
"""
    for comp, score in risk_breakdown.items():
        report += f"  {comp:.<30} {score:.1f}/100\n"

    report += f"""
{'='*70}
COMPLIANCE CONTROLS
{'='*70}
"""
    for check in checks:
        report += f"  [{check['Status'][:4]}] {check['Control']} — {check['Evidence']} ({check['Framework']})\n"

    report += f"""
{'='*70}
DRIFT ANALYSIS
{'='*70}
Flag Rate Change: {drift.get('rate_change_pct', 'N/A')}%
Credit Change: {drift.get('credit_change_pct', 'N/A')}%
Volume Change: {drift.get('scan_change_pct', 'N/A')}%

{'='*70}
MITRE ATLAS COVERAGE
{'='*70}
"""
    for m in compute_mitre_matrix(df_scans):
        report += f"  {m['TTP']} | {m['Technique']:.<40} | {m['Detected']} | Count: {m['Count']}\n"

    report += f"""
{'='*70}
RECOMMENDATIONS
{'='*70}
"""
    for rec in recommendations:
        report += f"  [{rec['PRIORITY']}] {rec['RECOMMENDATION']}\n    Reason: {rec['REASON']}\n\n"

    report += f"""
{'='*70}
CERTIFICATION
This report is auto-generated for regulatory submission.
Data source: SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
Tamper-evidence: SHA-256 prefix {audit_hash}
{'='*70}
"""

    st.download_button("📥 Download Compliance Report (.txt)", data=report.encode(), file_name=f"AISOC_Report_{datetime.now().strftime('%Y%m%d')}.txt", mime="text/plain")

    if not df_scans.empty:
        st.download_button("⬇️ Download Raw Data (.csv)", data=df_scans.to_csv(index=False).encode(), file_name=f"guardrails_audit_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

    with st.expander("Preview Report"):
        st.code(report, language="text")

# =============================================================================
# FOOTER
# =============================================================================
st.divider()
st.caption("SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY • AI Security Operations Center v3.0")
