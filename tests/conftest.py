# Shared pytest fixtures for AISOC test suite
# Co-authored with CoCo
import json
import random
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import pytest


USERS = ["SATISH", "PRIYA_ANALYST", "RAHUL_DEVOPS", "ANITA_DS", "VIKRAM_ADMIN",
         "DEEPAK_SRE", "MEERA_SOC", "ARJUN_MLENG", "KAVITHA_BA", "NIKHIL_BOT"]
SOURCES = ["CORTEX_CODE_SNOWSIGHT", "CORTEX_AGENT", "CORTEX_CODE_CLI",
           "CORTEX_CODE_DESKTOP", "SNOWFLAKE_INTELLIGENCE"]
TOOL_TYPES = ["sql_execute", "web_search", "server_mcp", "code_interpreter"]


@pytest.fixture
def empty_df():
    """Empty DataFrame with correct schema."""
    return pd.DataFrame(columns=[
        "USER_NAME", "AGENTIC_SOURCE", "REQUEST_ID", "PARENT_REQUEST_ID",
        "USAGE_TIME", "TOKEN_CREDITS", "TOKENS", "TOKENS_GRANULAR",
        "GUARDRAILS_SIGNAL", "GUARDRAIL_RESULTS", "ROLE_NAME"
    ])


@pytest.fixture
def clean_df():
    """200 clean scans — no flags, business hours, non-privileged."""
    random.seed(42)
    np.random.seed(42)
    now = datetime.now()
    rows = []
    for i in range(200):
        ts = now - timedelta(hours=random.uniform(0, 72))
        ts = ts.replace(hour=random.randint(9, 17), minute=random.randint(0, 59))
        rows.append({
            "USER_NAME": random.choice(USERS[:7]),
            "AGENTIC_SOURCE": random.choice(SOURCES),
            "REQUEST_ID": f"REQ-CLEAN-{i:05d}",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": ts,
            "TOKEN_CREDITS": round(random.uniform(0.0001, 0.005), 6),
            "TOKENS": random.randint(50, 500),
            "TOKENS_GRANULAR": json.dumps({"input": random.randint(40, 400), "output": random.randint(10, 100), "cache_read_input": random.randint(5, 50), "cache_write_input": random.randint(2, 20)}),
            "GUARDRAILS_SIGNAL": False,
            "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": f"t-{i}", "tool_type": random.choice(TOOL_TYPES), "indirect_prompt_injection": False, "token_count": random.randint(50, 500)}]),
            "ROLE_NAME": random.choice(["ANALYST_ROLE", "DATA_ENGINEER", "ML_ENGINEER"]),
        })
    return pd.DataFrame(rows)


@pytest.fixture
def high_risk_df():
    """300 scans — 25% flags, privileged roles, off-hours, nested chains."""
    random.seed(42)
    np.random.seed(42)
    now = datetime.now()
    rows = []
    for i in range(300):
        ts = now - timedelta(hours=random.uniform(0, 72))
        is_attack = i < 75
        is_privileged = i < 30
        is_off_hours = i < 40
        is_nested = i < 15

        if is_off_hours:
            ts = ts.replace(hour=random.choice([1, 2, 3, 4, 23, 0]))
        else:
            ts = ts.replace(hour=random.randint(9, 17))

        rows.append({
            "USER_NAME": "VIKRAM_ADMIN" if is_privileged else random.choice(USERS[:8]),
            "AGENTIC_SOURCE": "CORTEX_AGENT" if is_attack else random.choice(SOURCES),
            "REQUEST_ID": f"REQ-ATK-{i:05d}",
            "PARENT_REQUEST_ID": f"PARENT-{i % 8:04d}" if is_nested else None,
            "USAGE_TIME": ts,
            "TOKEN_CREDITS": round(random.uniform(0.01, 0.08), 6) if is_attack else round(random.uniform(0.0001, 0.005), 6),
            "TOKENS": random.randint(500, 2000) if is_attack else random.randint(50, 500),
            "TOKENS_GRANULAR": json.dumps({"input": random.randint(200, 1500), "output": random.randint(50, 500), "cache_read_input": random.randint(0, 100), "cache_write_input": random.randint(0, 30)}),
            "GUARDRAILS_SIGNAL": is_attack,
            "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": f"t-atk-{i}", "tool_type": random.choice(["web_search", "server_mcp"]) if is_attack else "sql_execute", "indirect_prompt_injection": is_attack, "token_count": random.randint(500, 2000) if is_attack else random.randint(50, 200)}]),
            "ROLE_NAME": random.choice(["ACCOUNTADMIN", "SYSADMIN"]) if is_privileged else random.choice(["ANALYST_ROLE", "DATA_ENGINEER", "ML_ENGINEER"]),
        })
    return pd.DataFrame(rows)


@pytest.fixture
def velocity_spike_df():
    """One user with 16x normal scan velocity in a single hour."""
    random.seed(42)
    now = datetime.now().replace(minute=0, second=0)
    rows = []
    # Baseline: 5 scans/hour for 24 hours
    for h in range(24):
        for s in range(5):
            rows.append({
                "USER_NAME": "SPIKE_USER",
                "AGENTIC_SOURCE": "CORTEX_AGENT",
                "REQUEST_ID": f"REQ-VEL-{h}-{s}",
                "PARENT_REQUEST_ID": None,
                "USAGE_TIME": now - timedelta(hours=h+1, minutes=random.randint(0, 59)),
                "TOKEN_CREDITS": 0.001,
                "TOKENS": 100,
                "TOKENS_GRANULAR": "{}",
                "GUARDRAILS_SIGNAL": False,
                "GUARDRAIL_RESULTS": "[]",
                "ROLE_NAME": "DATA_ENGINEER",
            })
    # Spike: 80 scans in current hour
    for s in range(80):
        rows.append({
            "USER_NAME": "SPIKE_USER",
            "AGENTIC_SOURCE": "CORTEX_AGENT",
            "REQUEST_ID": f"REQ-SPIKE-{s:03d}",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": now - timedelta(minutes=random.randint(0, 59)),
            "TOKEN_CREDITS": 0.002,
            "TOKENS": 200,
            "TOKENS_GRANULAR": "{}",
            "GUARDRAILS_SIGNAL": s < 20,
            "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": f"t-spike-{s}", "tool_type": "web_search", "indirect_prompt_injection": s < 20, "token_count": 300}]),
            "ROLE_NAME": "APP_ROLE",
        })
    return pd.DataFrame(rows)


@pytest.fixture
def insider_threat_df():
    """Privileged user operating at 3 AM with all flags."""
    random.seed(42)
    now = datetime.now()
    rows = []
    # Normal users
    for i in range(150):
        ts = now - timedelta(hours=random.uniform(0, 72))
        ts = ts.replace(hour=random.randint(9, 17))
        rows.append({
            "USER_NAME": random.choice(USERS[:5]),
            "AGENTIC_SOURCE": random.choice(SOURCES),
            "REQUEST_ID": f"REQ-INS-{i:04d}",
            "PARENT_REQUEST_ID": None,
            "USAGE_TIME": ts,
            "TOKEN_CREDITS": round(random.uniform(0.0001, 0.003), 6),
            "TOKENS": random.randint(50, 300),
            "TOKENS_GRANULAR": "{}",
            "GUARDRAILS_SIGNAL": False,
            "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": f"t-n-{i}", "tool_type": "sql_execute", "indirect_prompt_injection": False, "token_count": 100}]),
            "ROLE_NAME": "ANALYST_ROLE",
        })
    # Insider threat
    for i in range(30):
        ts = now - timedelta(hours=random.uniform(0, 48))
        ts = ts.replace(hour=random.choice([2, 3, 4]))
        rows.append({
            "USER_NAME": "VIKRAM_ADMIN",
            "AGENTIC_SOURCE": "CORTEX_CODE_CLI",
            "REQUEST_ID": f"REQ-INSIDER-{i:04d}",
            "PARENT_REQUEST_ID": f"PARENT-INS-{i % 5}" if i < 10 else None,
            "USAGE_TIME": ts,
            "TOKEN_CREDITS": round(random.uniform(0.05, 0.2), 6),
            "TOKENS": random.randint(1000, 5000),
            "TOKENS_GRANULAR": json.dumps({"input": 3000, "output": 2000, "cache_read_input": 0, "cache_write_input": 0}),
            "GUARDRAILS_SIGNAL": True,
            "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": f"t-ins-{i}", "tool_type": "server_mcp", "indirect_prompt_injection": True, "token_count": 3000}]),
            "ROLE_NAME": random.choice(["ACCOUNTADMIN", "SYSADMIN"]),
        })
    return pd.DataFrame(rows)
