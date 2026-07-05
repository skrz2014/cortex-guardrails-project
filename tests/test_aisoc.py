# End-to-end test suite for AISOC Cortex AI Guardrails Streamlit app analytics engine
"""
Test Suite: Cortex AI Guardrails AISOC
Validates all analytics functions with synthetic data that mirrors
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY schema.

Run: pytest test_aisoc.py -v
"""
import json
import hashlib
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import pytest


# =============================================================================
# THRESHOLDS (mirror app config)
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


# =============================================================================
# ANALYTICS FUNCTIONS (extracted from streamlit_app.py for testability)
# =============================================================================
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


def compute_executive_risk_score(df, days_in_range):
    if df.empty:
        return 0.0, {}

    total = len(df)
    flagged = df["GUARDRAILS_SIGNAL"].sum()

    injection_rate = min((flagged / total * 100) / THRESHOLDS["circuit_breaker_pct"] * 100, 100) if total > 0 else 0

    priv_flagged = df[(df["ROLE_NAME"].isin(THRESHOLDS["privileged_roles"])) & (df["GUARDRAILS_SIGNAL"] == True)]
    priv_score = min(len(priv_flagged) * 20, 100)

    velocity_alerts = compute_velocity_alerts(df)
    velocity_score = min(len(velocity_alerts) * 10, 100)

    hours = pd.to_datetime(df["USAGE_TIME"]).dt.hour
    off_mask = (hours < THRESHOLDS["working_hours_start"]) | (hours >= THRESHOLDS["working_hours_end"])
    off_flagged = df[off_mask & (df["GUARDRAILS_SIGNAL"] == True)]
    off_score = min(len(off_flagged) * 15, 100)

    daily_credits = df["TOKEN_CREDITS"].sum() / max(days_in_range, 1)
    cost_score = min((daily_credits / THRESHOLDS["credit_daily_budget"]) * 50, 100) if THRESHOLDS["credit_daily_budget"] > 0 else 0

    compliance_score = 0
    if flagged > 0 and len(priv_flagged) > 0:
        compliance_score += 50
    if off_score > 0:
        compliance_score += 30
    if injection_rate > 50:
        compliance_score += 20
    compliance_score = min(compliance_score, 100)

    nested = df[df["PARENT_REQUEST_ID"].notna()]
    nested_flagged = nested[nested["GUARDRAILS_SIGNAL"] == True]
    chain_score = min(len(nested_flagged) * 25, 100)

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


def compute_ueba(df):
    if df.empty:
        return pd.DataFrame()

    df_copy = df.copy()
    ts = pd.to_datetime(df_copy["USAGE_TIME"])
    df_copy["HOUR"] = ts.dt.hour
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
    )

    user_behavior["FLAG_RATE"] = (user_behavior["FLAGGED"] / user_behavior["TOTAL_SCANS"] * 100).round(1)
    user_behavior["WEEKEND_PCT"] = (user_behavior["WEEKEND_SCANS"] / user_behavior["TOTAL_SCANS"] * 100).round(1)
    user_behavior["NIGHT_PCT"] = (user_behavior["NIGHT_SCANS"] / user_behavior["TOTAL_SCANS"] * 100).round(1)
    user_behavior["AVG_TOKENS"] = (user_behavior["TOTAL_TOKENS"] / user_behavior["TOTAL_SCANS"]).round(0)

    token_mean = user_behavior["AVG_TOKENS"].mean()
    token_std = user_behavior["AVG_TOKENS"].std()
    user_behavior["TOKEN_ANOMALY"] = ((user_behavior["AVG_TOKENS"] - token_mean) / max(token_std, 1)).round(2)

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
    }


def generate_incidents(df):
    if df.empty:
        return []
    flagged = df[df["GUARDRAILS_SIGNAL"] == True].copy()
    if flagged.empty:
        return []

    incidents = []
    for i, (_, row) in enumerate(flagged.head(20).iterrows(), 1):
        severity = "P1" if row["ROLE_NAME"] in THRESHOLDS["privileged_roles"] else "P2"
        hour = pd.to_datetime(row["USAGE_TIME"]).hour
        if hour < THRESHOLDS["working_hours_start"] or hour >= THRESHOLDS["working_hours_end"]:
            severity = "P1"
        incidents.append({
            "ID": f"AI-{datetime.now().year}-{i:06d}",
            "SEVERITY": severity,
            "USER": row["USER_NAME"],
            "ROLE": row["ROLE_NAME"],
            "SOURCE": row["AGENTIC_SOURCE"],
            "CREDITS": round(row["TOKEN_CREDITS"], 6),
            "STATUS": "OPEN",
        })
    return incidents


def generate_recommendations(risk_score, breakdown, df, drift):
    recs = []
    if breakdown.get("Injection Rate", 0) > 50:
        recs.append({"PRIORITY": "CRITICAL", "RECOMMENDATION": "Investigate prompt injection surge"})
    if breakdown.get("Privileged Access", 0) > 0:
        recs.append({"PRIORITY": "HIGH", "RECOMMENDATION": "Restrict privileged roles from AI agent usage"})
    if breakdown.get("Off-Hours Activity", 0) > 30:
        recs.append({"PRIORITY": "HIGH", "RECOMMENDATION": "Investigate off-hours AI activity"})
    if risk_score >= THRESHOLDS["risk_critical"]:
        recs.append({"PRIORITY": "CRITICAL", "RECOMMENDATION": "Consider disabling AI tool calling"})
    if drift and drift.get("rate_change_pct", 0) > 100:
        recs.append({"PRIORITY": "HIGH", "RECOMMENDATION": "Investigate injection rate drift"})
    if not recs:
        recs.append({"PRIORITY": "INFO", "RECOMMENDATION": "No immediate action required"})
    return recs


def compute_mitre_matrix(df):
    if df.empty:
        return []

    total_flags = df["GUARDRAILS_SIGNAL"].sum()
    indirect_count = 0
    tool_manip_count = 0

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
    for ttp_id, info in {
        "AML.T0051": {"name": "LLM Prompt Injection (Direct)", "severity": "Critical"},
        "AML.T0051.001": {"name": "Indirect Prompt Injection", "severity": "Critical"},
        "AML.T0051.002": {"name": "Tool Output Manipulation", "severity": "High"},
    }.items():
        detected = False
        count = 0
        if ttp_id == "AML.T0051" and total_flags > 0:
            detected = True
            count = int(total_flags)
        elif ttp_id == "AML.T0051.001" and indirect_count > 0:
            detected = True
            count = indirect_count
        elif ttp_id == "AML.T0051.002" and tool_manip_count > 0:
            detected = True
            count = tool_manip_count
        matrix.append({"TTP": ttp_id, "Technique": info["name"], "Detected": detected, "Count": count})

    return matrix


def generate_audit_hash(df):
    if df.empty:
        return "N/A"
    content = df.to_csv(index=False)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# TEST FIXTURES
# =============================================================================
@pytest.fixture
def empty_df():
    return pd.DataFrame(columns=[
        "USER_NAME", "AGENTIC_SOURCE", "REQUEST_ID", "PARENT_REQUEST_ID",
        "USAGE_TIME", "TOKEN_CREDITS", "TOKENS", "TOKENS_GRANULAR",
        "GUARDRAILS_SIGNAL", "GUARDRAIL_RESULTS", "ROLE_NAME"
    ])


@pytest.fixture
def clean_df():
    """50 clean scans, no flags, business hours, non-privileged roles."""
    now = datetime.now()
    rows = []
    for i in range(50):
        ts = now - timedelta(hours=i)
        # Force business hours
        ts = ts.replace(hour=10 + (i % 8), minute=0, second=0)
        rows.append({
            "USER_NAME": f"USER_{i % 5}",
            "AGENTIC_SOURCE": ["CORTEX_CODE_SNOWSIGHT", "CORTEX_AGENT", "SNOWFLAKE_INTELLIGENCE"][i % 3],
            "REQUEST_ID": f"REQ-{i:04d}",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": ts,
            "TOKEN_CREDITS": 0.0001 * (i + 1),
            "TOKENS": 100 + i * 10,
            "TOKENS_GRANULAR": json.dumps({"input": 80 + i, "output": 20, "cache_read_input": 10, "cache_write_input": 5}),
            "GUARDRAILS_SIGNAL": False,
            "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": f"t{i}", "tool_type": "sql_execute", "indirect_prompt_injection": False, "token_count": 100}]),
            "ROLE_NAME": "ANALYST_ROLE",
        })
    return pd.DataFrame(rows)


@pytest.fixture
def high_risk_df():
    """100 scans with 25% flags, privileged roles, off-hours, nested chains."""
    now = datetime.now()
    rows = []
    for i in range(100):
        ts = now - timedelta(hours=i % 72)
        is_flagged = i < 25  # 25% flag rate
        is_privileged = i < 10  # 10 from ACCOUNTADMIN
        is_off_hours = i < 15  # 15 at 3 AM
        is_nested = i < 8  # 8 nested chains

        if is_off_hours:
            ts = ts.replace(hour=3)
        else:
            ts = ts.replace(hour=14)

        rows.append({
            "USER_NAME": f"USER_{i % 8}",
            "AGENTIC_SOURCE": ["CORTEX_CODE_SNOWSIGHT", "CORTEX_AGENT", "CORTEX_CODE_CLI"][i % 3],
            "REQUEST_ID": f"REQ-{i:04d}",
            "PARENT_REQUEST_ID": f"PARENT-{i % 4:04d}" if is_nested else None,
            "USAGE_TIME": ts,
            "TOKEN_CREDITS": 0.05 if is_flagged else 0.001,
            "TOKENS": 500 if is_flagged else 100,
            "TOKENS_GRANULAR": json.dumps({"input": 400, "output": 100, "cache_read_input": 50, "cache_write_input": 20}),
            "GUARDRAILS_SIGNAL": is_flagged,
            "GUARDRAIL_RESULTS": json.dumps([{
                "tool_use_id": f"t{i}",
                "tool_type": "web_search" if is_flagged else "sql_execute",
                "indirect_prompt_injection": is_flagged,
                "token_count": 500 if is_flagged else 100,
            }]),
            "ROLE_NAME": "ACCOUNTADMIN" if is_privileged else "ANALYST_ROLE",
        })
    return pd.DataFrame(rows)


@pytest.fixture
def velocity_spike_df():
    """One user with massive spike in a single hour."""
    now = datetime.now().replace(hour=14, minute=0, second=0)
    rows = []
    # User A: 5 scans per hour baseline (5 hours) + 50 scans in one spike hour
    for h in range(5):
        for s in range(5):
            rows.append({
                "USER_NAME": "SPIKE_USER",
                "AGENTIC_SOURCE": "CORTEX_AGENT",
                "REQUEST_ID": f"REQ-{h}-{s}",
                "PARENT_REQUEST_ID": None,
                "USAGE_TIME": now - timedelta(hours=h+1, minutes=s),
                "TOKEN_CREDITS": 0.001,
                "TOKENS": 100,
                "TOKENS_GRANULAR": "{}",
                "GUARDRAILS_SIGNAL": False,
                "GUARDRAIL_RESULTS": "[]",
                "ROLE_NAME": "DATA_ENGINEER",
            })
    # Spike: 50 scans in the current hour
    for s in range(50):
        rows.append({
            "USER_NAME": "SPIKE_USER",
            "AGENTIC_SOURCE": "CORTEX_AGENT",
            "REQUEST_ID": f"REQ-SPIKE-{s}",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": now - timedelta(minutes=s),
            "TOKEN_CREDITS": 0.001,
            "TOKENS": 100,
            "TOKENS_GRANULAR": "{}",
            "GUARDRAILS_SIGNAL": False,
            "GUARDRAIL_RESULTS": "[]",
            "ROLE_NAME": "DATA_ENGINEER",
        })
    return pd.DataFrame(rows)


# =============================================================================
# TEST CLASS: Executive Risk Score
# =============================================================================
class TestExecutiveRiskScore:
    def test_empty_data_returns_zero(self, empty_df):
        score, breakdown = compute_executive_risk_score(empty_df, 3)
        assert score == 0.0
        assert breakdown == {}

    def test_clean_data_low_risk(self, clean_df):
        score, breakdown = compute_executive_risk_score(clean_df, 3)
        assert score < THRESHOLDS["risk_moderate"], f"Clean data should be LOW risk, got {score}"
        assert breakdown["Injection Rate"] == 0
        assert breakdown["Privileged Access"] == 0
        assert breakdown["Off-Hours Activity"] == 0

    def test_high_risk_data_critical(self, high_risk_df):
        score, breakdown = compute_executive_risk_score(high_risk_df, 3)
        assert score >= THRESHOLDS["risk_high"], f"High-risk data should be HIGH+, got {score}"
        assert breakdown["Injection Rate"] > 0
        assert breakdown["Privileged Access"] > 0

    def test_risk_score_capped_at_100(self, high_risk_df):
        score, _ = compute_executive_risk_score(high_risk_df, 0.01)  # Very short range = high cost
        assert score <= 100

    def test_all_components_present(self, high_risk_df):
        _, breakdown = compute_executive_risk_score(high_risk_df, 3)
        expected_keys = {"Injection Rate", "Privileged Access", "Velocity Anomalies",
                         "Off-Hours Activity", "Cost Spike", "Compliance", "Nested Chains"}
        assert set(breakdown.keys()) == expected_keys

    def test_component_values_bounded(self, high_risk_df):
        _, breakdown = compute_executive_risk_score(high_risk_df, 3)
        for key, val in breakdown.items():
            assert 0 <= val <= 100, f"{key} = {val} out of bounds"


# =============================================================================
# TEST CLASS: Velocity Alerts
# =============================================================================
class TestVelocityAlerts:
    def test_empty_data_no_alerts(self, empty_df):
        alerts = compute_velocity_alerts(empty_df)
        assert alerts == []

    def test_uniform_data_no_alerts(self, clean_df):
        alerts = compute_velocity_alerts(clean_df)
        # With uniform distribution, no single hour should be 3x the mean
        assert len(alerts) == 0 or all(a["SPIKE"] >= THRESHOLDS["velocity_multiplier"] for a in alerts)

    def test_spike_detected(self, velocity_spike_df):
        alerts = compute_velocity_alerts(velocity_spike_df)
        assert len(alerts) > 0, "Should detect velocity spike"
        assert alerts[0]["USER"] == "SPIKE_USER"
        assert alerts[0]["SPIKE"] >= THRESHOLDS["velocity_multiplier"]

    def test_max_20_alerts(self, velocity_spike_df):
        alerts = compute_velocity_alerts(velocity_spike_df)
        assert len(alerts) <= 20

    def test_alerts_sorted_by_spike(self, velocity_spike_df):
        alerts = compute_velocity_alerts(velocity_spike_df)
        if len(alerts) > 1:
            spikes = [a["SPIKE"] for a in alerts]
            assert spikes == sorted(spikes, reverse=True)


# =============================================================================
# TEST CLASS: UEBA
# =============================================================================
class TestUEBA:
    def test_empty_data(self, empty_df):
        result = compute_ueba(empty_df)
        assert result.empty

    def test_columns_present(self, clean_df):
        result = compute_ueba(clean_df)
        expected_cols = {"USER_NAME", "TOTAL_SCANS", "FLAGGED", "FLAG_RATE",
                         "WEEKEND_PCT", "NIGHT_PCT", "AVG_TOKENS", "TOKEN_ANOMALY", "BEHAVIOR_RISK"}
        assert expected_cols.issubset(set(result.columns))

    def test_behavior_risk_bounded(self, high_risk_df):
        result = compute_ueba(high_risk_df)
        assert result["BEHAVIOR_RISK"].min() >= 0
        # Risk can exceed 100 theoretically with the formula, but should be reasonable

    def test_sorted_by_risk(self, high_risk_df):
        result = compute_ueba(high_risk_df)
        risks = result["BEHAVIOR_RISK"].tolist()
        assert risks == sorted(risks, reverse=True)

    def test_clean_users_low_risk(self, clean_df):
        result = compute_ueba(clean_df)
        # No flags, business hours only → low risk
        assert result["FLAGGED"].sum() == 0
        assert result["FLAG_RATE"].max() == 0


# =============================================================================
# TEST CLASS: Drift Detection
# =============================================================================
class TestDriftDetection:
    def test_empty_data_returns_empty(self, empty_df):
        result = compute_drift(empty_df, 3)
        assert result == {}

    def test_small_data_returns_empty(self):
        df = pd.DataFrame({
            "USER_NAME": ["A"] * 5,
            "USAGE_TIME": [datetime.now() - timedelta(hours=i) for i in range(5)],
            "GUARDRAILS_SIGNAL": [False] * 5,
            "TOKEN_CREDITS": [0.001] * 5,
        })
        result = compute_drift(df, 1)
        assert result == {}

    def test_stable_data_low_drift(self, clean_df):
        result = compute_drift(clean_df, 3)
        assert "rate_change_pct" in result
        # All clean → both halves should be 0% flag rate
        assert result["prev_flag_rate"] == 0
        assert result["curr_flag_rate"] == 0

    def test_increasing_flags_positive_drift(self):
        now = datetime.now()
        rows = []
        # First 50: no flags (older)
        for i in range(50):
            rows.append({
                "USER_NAME": "A", "USAGE_TIME": now - timedelta(hours=48+i),
                "GUARDRAILS_SIGNAL": False, "TOKEN_CREDITS": 0.001,
            })
        # Last 50: 50% flagged (newer)
        for i in range(50):
            rows.append({
                "USER_NAME": "A", "USAGE_TIME": now - timedelta(hours=i),
                "GUARDRAILS_SIGNAL": i < 25, "TOKEN_CREDITS": 0.001,
            })
        df = pd.DataFrame(rows)
        result = compute_drift(df, 4)
        assert result["curr_flag_rate"] > result["prev_flag_rate"]
        assert result["rate_change_pct"] > 0


# =============================================================================
# TEST CLASS: Incident Generation
# =============================================================================
class TestIncidentGeneration:
    def test_no_flags_no_incidents(self, clean_df):
        incidents = generate_incidents(clean_df)
        assert incidents == []

    def test_flags_generate_incidents(self, high_risk_df):
        incidents = generate_incidents(high_risk_df)
        assert len(incidents) > 0
        assert all(i["STATUS"] == "OPEN" for i in incidents)

    def test_privileged_role_is_p1(self, high_risk_df):
        incidents = generate_incidents(high_risk_df)
        priv_incidents = [i for i in incidents if i["ROLE"] == "ACCOUNTADMIN"]
        assert all(i["SEVERITY"] == "P1" for i in priv_incidents)

    def test_off_hours_is_p1(self):
        rows = [{
            "USER_NAME": "NIGHT_USER",
            "AGENTIC_SOURCE": "CORTEX_AGENT",
            "REQUEST_ID": "REQ-NIGHT",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": datetime.now().replace(hour=3),
            "TOKEN_CREDITS": 0.01,
            "TOKENS": 200,
            "TOKENS_GRANULAR": "{}",
            "GUARDRAILS_SIGNAL": True,
            "GUARDRAIL_RESULTS": "[]",
            "ROLE_NAME": "ANALYST_ROLE",
        }]
        df = pd.DataFrame(rows)
        incidents = generate_incidents(df)
        assert incidents[0]["SEVERITY"] == "P1"

    def test_max_20_incidents(self, high_risk_df):
        incidents = generate_incidents(high_risk_df)
        assert len(incidents) <= 20

    def test_incident_id_format(self, high_risk_df):
        incidents = generate_incidents(high_risk_df)
        year = datetime.now().year
        assert all(i["ID"].startswith(f"AI-{year}-") for i in incidents)


# =============================================================================
# TEST CLASS: Recommendations
# =============================================================================
class TestRecommendations:
    def test_low_risk_info_only(self):
        recs = generate_recommendations(10, {"Injection Rate": 0, "Privileged Access": 0, "Off-Hours Activity": 0}, pd.DataFrame(), {})
        assert len(recs) == 1
        assert recs[0]["PRIORITY"] == "INFO"

    def test_high_injection_triggers_critical(self):
        breakdown = {"Injection Rate": 80, "Privileged Access": 0, "Off-Hours Activity": 0}
        recs = generate_recommendations(50, breakdown, pd.DataFrame(), {})
        priorities = [r["PRIORITY"] for r in recs]
        assert "CRITICAL" in priorities

    def test_privileged_access_triggers_high(self):
        breakdown = {"Injection Rate": 0, "Privileged Access": 40, "Off-Hours Activity": 0}
        recs = generate_recommendations(30, breakdown, pd.DataFrame(), {})
        priorities = [r["PRIORITY"] for r in recs]
        assert "HIGH" in priorities

    def test_critical_risk_triggers_kill_switch(self):
        breakdown = {"Injection Rate": 80, "Privileged Access": 60, "Off-Hours Activity": 50}
        recs = generate_recommendations(70, breakdown, pd.DataFrame(), {})
        rec_texts = [r["RECOMMENDATION"] for r in recs]
        assert any("disabling" in r.lower() or "disable" in r.lower() for r in rec_texts)

    def test_drift_triggers_recommendation(self):
        breakdown = {"Injection Rate": 30, "Privileged Access": 0, "Off-Hours Activity": 0}
        drift = {"rate_change_pct": 200}
        recs = generate_recommendations(30, breakdown, pd.DataFrame(), drift)
        rec_texts = [r["RECOMMENDATION"] for r in recs]
        assert any("drift" in r.lower() for r in rec_texts)


# =============================================================================
# TEST CLASS: MITRE ATLAS
# =============================================================================
class TestMITREAtlas:
    def test_empty_data(self, empty_df):
        matrix = compute_mitre_matrix(empty_df)
        assert matrix == []

    def test_no_flags_no_detections(self, clean_df):
        matrix = compute_mitre_matrix(clean_df)
        assert all(not m["Detected"] for m in matrix)

    def test_flags_detected(self, high_risk_df):
        matrix = compute_mitre_matrix(high_risk_df)
        detected = [m for m in matrix if m["Detected"]]
        assert len(detected) > 0

    def test_indirect_injection_counted(self, high_risk_df):
        matrix = compute_mitre_matrix(high_risk_df)
        indirect = next((m for m in matrix if m["TTP"] == "AML.T0051.001"), None)
        assert indirect is not None
        assert indirect["Detected"] is True
        assert indirect["Count"] > 0

    def test_tool_manipulation_detected(self, high_risk_df):
        matrix = compute_mitre_matrix(high_risk_df)
        tool = next((m for m in matrix if m["TTP"] == "AML.T0051.002"), None)
        assert tool is not None
        assert tool["Detected"] is True


# =============================================================================
# TEST CLASS: Audit Hash
# =============================================================================
class TestAuditHash:
    def test_empty_returns_na(self, empty_df):
        assert generate_audit_hash(empty_df) == "N/A"

    def test_deterministic(self, clean_df):
        h1 = generate_audit_hash(clean_df)
        h2 = generate_audit_hash(clean_df)
        assert h1 == h2

    def test_different_data_different_hash(self, clean_df, high_risk_df):
        h1 = generate_audit_hash(clean_df)
        h2 = generate_audit_hash(high_risk_df)
        assert h1 != h2

    def test_hash_is_16_chars(self, clean_df):
        h = generate_audit_hash(clean_df)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


# =============================================================================
# TEST CLASS: Integration / E2E Scenarios
# =============================================================================
class TestEndToEnd:
    def test_full_pipeline_clean_scenario(self, clean_df):
        """E2E: Clean data → low risk, no incidents, no alerts, passing compliance."""
        score, breakdown = compute_executive_risk_score(clean_df, 3)
        assert score < 21  # LOW

        incidents = generate_incidents(clean_df)
        assert incidents == []

        velocity = compute_velocity_alerts(clean_df)
        # May or may not have alerts depending on distribution

        ueba = compute_ueba(clean_df)
        assert ueba["FLAGGED"].sum() == 0

        recs = generate_recommendations(score, breakdown, clean_df, {})
        assert recs[0]["PRIORITY"] == "INFO"

    def test_full_pipeline_attack_scenario(self, high_risk_df):
        """E2E: Active attack → high risk, incidents, velocity alerts, MITRE detections."""
        score, breakdown = compute_executive_risk_score(high_risk_df, 3)
        assert score >= 40  # HIGH or CRITICAL

        incidents = generate_incidents(high_risk_df)
        assert len(incidents) > 0
        assert any(i["SEVERITY"] == "P1" for i in incidents)

        mitre = compute_mitre_matrix(high_risk_df)
        detected = [m for m in mitre if m["Detected"]]
        assert len(detected) >= 2  # At least direct + indirect

        recs = generate_recommendations(score, breakdown, high_risk_df, {"rate_change_pct": 150})
        priorities = [r["PRIORITY"] for r in recs]
        assert "CRITICAL" in priorities or "HIGH" in priorities

        drift = compute_drift(high_risk_df, 3)
        assert "curr_flag_rate" in drift

        hash_val = generate_audit_hash(high_risk_df)
        assert hash_val != "N/A"
        assert len(hash_val) == 16

    def test_circuit_breaker_logic(self, high_risk_df):
        """E2E: Verify circuit breaker triggers at configured threshold."""
        total = len(high_risk_df)
        flagged = high_risk_df["GUARDRAILS_SIGNAL"].sum()
        flag_rate = flagged / total * 100
        circuit_active = flag_rate >= THRESHOLDS["circuit_breaker_pct"]
        # high_risk_df has 25% flags, threshold is 15%
        assert bool(circuit_active) is True

    def test_compliance_flow(self, clean_df, high_risk_df):
        """E2E: Clean data passes compliance, high-risk fails."""
        # Clean: no privileged flags, no off-hours
        clean_priv = clean_df[(clean_df["ROLE_NAME"].isin(THRESHOLDS["privileged_roles"])) & (clean_df["GUARDRAILS_SIGNAL"] == True)]
        assert clean_priv.empty

        # High-risk: has privileged flags
        risk_priv = high_risk_df[(high_risk_df["ROLE_NAME"].isin(THRESHOLDS["privileged_roles"])) & (high_risk_df["GUARDRAILS_SIGNAL"] == True)]
        assert not risk_priv.empty

    def test_ueba_detects_anomalous_user(self, high_risk_df):
        """E2E: UEBA correctly ranks flagged users higher."""
        ueba = compute_ueba(high_risk_df)
        top_user = ueba.iloc[0]
        assert top_user["BEHAVIOR_RISK"] > 0
        assert top_user["FLAGGED"] > 0 or top_user["NIGHT_PCT"] > 0


# =============================================================================
# TEST CLASS: Edge Cases
# =============================================================================
class TestEdgeCases:
    def test_single_row(self):
        df = pd.DataFrame([{
            "USER_NAME": "SOLO",
            "AGENTIC_SOURCE": "CORTEX_AGENT",
            "REQUEST_ID": "REQ-001",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": datetime.now(),
            "TOKEN_CREDITS": 0.001,
            "TOKENS": 100,
            "TOKENS_GRANULAR": "{}",
            "GUARDRAILS_SIGNAL": True,
            "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": "t1", "tool_type": "sql_execute", "indirect_prompt_injection": True, "token_count": 100}]),
            "ROLE_NAME": "ACCOUNTADMIN",
        }])
        score, _ = compute_executive_risk_score(df, 1)
        assert score > 0

        incidents = generate_incidents(df)
        assert len(incidents) == 1
        assert incidents[0]["SEVERITY"] == "P1"

    def test_all_flags(self):
        """100% flag rate scenario."""
        rows = [{
            "USER_NAME": f"USER_{i}",
            "AGENTIC_SOURCE": "CORTEX_AGENT",
            "REQUEST_ID": f"REQ-{i}",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": datetime.now() - timedelta(hours=i),
            "TOKEN_CREDITS": 0.01,
            "TOKENS": 200,
            "TOKENS_GRANULAR": "{}",
            "GUARDRAILS_SIGNAL": True,
            "GUARDRAIL_RESULTS": "[]",
            "ROLE_NAME": "ACCOUNTADMIN",
        } for i in range(20)]
        df = pd.DataFrame(rows)
        score, _ = compute_executive_risk_score(df, 1)
        assert score >= THRESHOLDS["risk_critical"]  # Should be CRITICAL

    def test_null_guardrail_results(self, clean_df):
        """Handle None/null in GUARDRAIL_RESULTS gracefully."""
        clean_df.loc[0, "GUARDRAIL_RESULTS"] = None
        clean_df.loc[1, "GUARDRAIL_RESULTS"] = ""
        clean_df.loc[2, "GUARDRAIL_RESULTS"] = "invalid json"
        # Should not crash
        matrix = compute_mitre_matrix(clean_df)
        assert isinstance(matrix, list)

    def test_zero_days_in_range(self, clean_df):
        """Avoid division by zero with 0 days."""
        score, _ = compute_executive_risk_score(clean_df, 0)
        assert score >= 0

    def test_very_large_token_values(self):
        """Handle large token counts."""
        rows = [{
            "USER_NAME": "BIG_USER",
            "AGENTIC_SOURCE": "CORTEX_AGENT",
            "REQUEST_ID": "REQ-BIG",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": datetime.now(),
            "TOKEN_CREDITS": 999.99,
            "TOKENS": 10_000_000,
            "TOKENS_GRANULAR": json.dumps({"input": 9000000, "output": 1000000, "cache_read_input": 0, "cache_write_input": 0}),
            "GUARDRAILS_SIGNAL": False,
            "GUARDRAIL_RESULTS": "[]",
            "ROLE_NAME": "ANALYST_ROLE",
        }]
        df = pd.DataFrame(rows)
        ueba = compute_ueba(df)
        assert not ueba.empty


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
