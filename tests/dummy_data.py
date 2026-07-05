# Dummy data generator module for AISOC testing and demo mode
"""
Generates synthetic data matching SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY schema.

Usage:
    from tests.dummy_data import generate_scenario
    df = generate_scenario("attack")  # or "clean", "velocity", "insider", "drift"
"""
import json
import random
from datetime import datetime, timedelta

import pandas as pd
import numpy as np


USERS = ["SATISH", "PRIYA_ANALYST", "RAHUL_DEVOPS", "ANITA_DS", "VIKRAM_ADMIN",
         "DEEPAK_SRE", "MEERA_SOC", "ARJUN_MLENG", "KAVITHA_BA", "NIKHIL_BOT"]
SOURCES = ["CORTEX_CODE_SNOWSIGHT", "CORTEX_AGENT", "CORTEX_CODE_CLI",
           "CORTEX_CODE_DESKTOP", "SNOWFLAKE_INTELLIGENCE"]
TOOL_TYPES = ["sql_execute", "web_search", "server_mcp", "code_interpreter"]
PRIVILEGED_ROLES = ["ACCOUNTADMIN", "SYSADMIN", "SECURITYADMIN"]
STANDARD_ROLES = ["ANALYST_ROLE", "DATA_ENGINEER", "ML_ENGINEER", "APP_ROLE", "READER_ROLE"]


def _make_row(i, ts, is_attack, is_privileged, is_off_hours, is_nested):
    if is_off_hours:
        ts = ts.replace(hour=random.choice([0, 1, 2, 3, 4, 23]))
    elif is_attack:
        ts = ts.replace(hour=random.randint(9, 17))
    else:
        ts = ts.replace(hour=random.randint(8, 18))

    user = "VIKRAM_ADMIN" if is_privileged else random.choice(USERS[:8])
    role = random.choice(PRIVILEGED_ROLES[:2]) if is_privileged else random.choice(STANDARD_ROLES)
    source = "CORTEX_AGENT" if is_attack else random.choice(SOURCES)
    tool = random.choice(["web_search", "server_mcp"]) if is_attack else random.choice(TOOL_TYPES)

    return {
        "USER_NAME": user,
        "AGENTIC_SOURCE": source,
        "REQUEST_ID": f"REQ-{i:06d}",
        "PARENT_REQUEST_ID": f"PARENT-{i % 8:04d}" if is_nested else None,
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
            "tool_use_id": f"tool-{i:06d}",
            "tool_type": tool,
            "indirect_prompt_injection": is_attack,
            "token_count": random.randint(500, 3000) if is_attack else random.randint(50, 300),
        }]),
        "ROLE_NAME": role,
    }


def generate_scenario(scenario: str = "attack", n: int = 500, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic guardrail data for a given scenario.

    Args:
        scenario: One of "clean", "attack", "velocity", "insider", "drift"
        n: Number of records
        seed: Random seed for reproducibility

    Returns:
        DataFrame matching CORTEX_AI_GUARDRAILS_USAGE_HISTORY schema
    """
    random.seed(seed)
    np.random.seed(seed)
    now = datetime.now()

    if scenario == "clean":
        rows = []
        for i in range(n):
            ts = now - timedelta(hours=random.uniform(0, 72))
            rows.append(_make_row(i, ts, False, False, False, False))
        return pd.DataFrame(rows)

    elif scenario == "attack":
        rows = []
        attack_pct = 0.20
        priv_pct = 0.08
        offhours_pct = 0.10
        nested_pct = 0.04
        for i in range(n):
            ts = now - timedelta(hours=random.uniform(0, 72))
            rows.append(_make_row(
                i, ts,
                is_attack=i < int(n * attack_pct),
                is_privileged=i < int(n * priv_pct),
                is_off_hours=i < int(n * offhours_pct),
                is_nested=i < int(n * nested_pct),
            ))
        return pd.DataFrame(rows)

    elif scenario == "velocity":
        rows = []
        # Baseline: 5 users, 5 scans/hour for 24 hours
        for h in range(24):
            for user in USERS[:5]:
                for s in range(random.randint(3, 7)):
                    rows.append({
                        "USER_NAME": user, "AGENTIC_SOURCE": "CORTEX_AGENT",
                        "REQUEST_ID": f"REQ-VEL-{h}-{user[:3]}-{s}",
                        "PARENT_REQUEST_ID": None,
                        "USAGE_TIME": now - timedelta(hours=h+1, minutes=random.randint(0, 59)),
                        "TOKEN_CREDITS": 0.001, "TOKENS": 100, "TOKENS_GRANULAR": "{}",
                        "GUARDRAILS_SIGNAL": False, "GUARDRAIL_RESULTS": "[]",
                        "ROLE_NAME": "DATA_ENGINEER",
                    })
        # Spike: NIKHIL_BOT 80 scans in 1 hour
        for s in range(80):
            rows.append({
                "USER_NAME": "NIKHIL_BOT", "AGENTIC_SOURCE": "CORTEX_AGENT",
                "REQUEST_ID": f"REQ-SPIKE-{s:03d}",
                "PARENT_REQUEST_ID": None,
                "USAGE_TIME": now - timedelta(minutes=random.randint(0, 59)),
                "TOKEN_CREDITS": 0.002, "TOKENS": 200, "TOKENS_GRANULAR": "{}",
                "GUARDRAILS_SIGNAL": s < 20,
                "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": f"t-sp-{s}", "tool_type": "web_search", "indirect_prompt_injection": s < 20, "token_count": 300}]),
                "ROLE_NAME": "APP_ROLE",
            })
        return pd.DataFrame(rows)

    elif scenario == "insider":
        rows = []
        # Normal baseline
        for i in range(int(n * 0.8)):
            ts = now - timedelta(hours=random.uniform(0, 72))
            rows.append(_make_row(i, ts, False, False, False, False))
        # Insider: VIKRAM_ADMIN at 3 AM
        for i in range(int(n * 0.2)):
            ts = now - timedelta(hours=random.uniform(0, 48))
            ts = ts.replace(hour=random.choice([2, 3, 4]))
            rows.append({
                "USER_NAME": "VIKRAM_ADMIN", "AGENTIC_SOURCE": "CORTEX_CODE_CLI",
                "REQUEST_ID": f"REQ-INS-{i:04d}",
                "PARENT_REQUEST_ID": f"PARENT-INS-{i%5}" if i < 10 else None,
                "USAGE_TIME": ts,
                "TOKEN_CREDITS": round(random.uniform(0.05, 0.2), 6),
                "TOKENS": random.randint(1000, 5000),
                "TOKENS_GRANULAR": json.dumps({"input": 3000, "output": 2000, "cache_read_input": 0, "cache_write_input": 0}),
                "GUARDRAILS_SIGNAL": True,
                "GUARDRAIL_RESULTS": json.dumps([{"tool_use_id": f"t-ins-{i}", "tool_type": "server_mcp", "indirect_prompt_injection": True, "token_count": 3000}]),
                "ROLE_NAME": random.choice(["ACCOUNTADMIN", "SYSADMIN"]),
            })
        return pd.DataFrame(rows)

    elif scenario == "drift":
        rows = []
        half = n // 2
        # First half: clean (old)
        for i in range(half):
            ts = now - timedelta(days=random.uniform(3, 6))
            rows.append(_make_row(i, ts, False, False, False, False))
        # Second half: 40% flagged (recent)
        for i in range(half):
            ts = now - timedelta(days=random.uniform(0, 3))
            is_attack = i < int(half * 0.4)
            rows.append(_make_row(half + i, ts, is_attack, is_attack and i < 10, False, False))
        return pd.DataFrame(rows)

    else:
        raise ValueError(f"Unknown scenario: {scenario}. Use: clean, attack, velocity, insider, drift")


if __name__ == "__main__":
    for s in ["clean", "attack", "velocity", "insider", "drift"]:
        df = generate_scenario(s)
        flagged = df["GUARDRAILS_SIGNAL"].sum()
        print(f"{s:>10}: {len(df):>4} rows, {int(flagged):>3} flagged ({flagged/len(df)*100:.1f}%)")
