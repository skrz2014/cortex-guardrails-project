<div align="center">

# 🛡️ Cortex AI Guardrails — Enterprise AISOC

**Real-time AI Security Operations Center for Snowflake Cortex AI Guardrails**

[![Snowflake](https://img.shields.io/badge/Snowflake-29B5E8?style=flat&logo=snowflake&logoColor=white)](https://www.snowflake.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-50%20passed-brightgreen)](tests/)

</div>

---

## Overview

A production-grade monitoring solution built on Snowflake's [`CORTEX_AI_GUARDRAILS_USAGE_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/cortex_ai_guardrails_usage_history) view. Provides enterprise-level observability into prompt injection detection, credit consumption, and behavioral analytics across all Cortex AI workloads.

### Key Capabilities

| Feature | Description |
|---------|-------------|
| **Executive Risk Scoring** | Composite 0-100 risk score with weighted breakdown |
| **Incident Management** | Auto-generated P1/P2 incidents with visual timeline |
| **UEBA Analytics** | Behavioral patterns — off-hours, token anomalies, velocity |
| **MITRE ATLAS Mapping** | TTP detection matrix with real-time counts |
| **Compliance Reporting** | 6 automated controls mapped to 8 regulatory frameworks |
| **Cost Analytics** | Chargeback, forecasting, cache efficiency metrics |
| **Kill Switch** | Emergency SQL commands for incident response |
| **Demo Mode** | 500 synthetic records for testing without live data |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Snowflake Platform                         │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌────────────────────┐  │
│  │ Cortex   │──▶│  Guardrail   │──▶│ USAGE_HISTORY View │  │
│  │ AI Agent │   │  Scan Engine │   │ (Account Usage)    │  │
│  └──────────┘   └──────────────┘   └─────────┬──────────┘  │
│                                               │              │
│  ┌────────────────────────────────────────────▼──────────┐  │
│  │              AISOC Streamlit Dashboard                  │  │
│  │  ┌─────────┬──────────┬────────┬──────────┬────────┐  │  │
│  │  │Executive│Incidents │  UEBA  │Compliance│  Cost  │  │  │
│  │  └─────────┴──────────┴────────┴──────────┴────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Infrastructure: Alerts │ Dynamic Tables │ Tasks        │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
cortex-guardrails-project/
├── streamlit-app/                      # AISOC Dashboard (1300+ lines)
│   ├── streamlit_app.py                # 10-tab enterprise dashboard
│   ├── snowflake.yml                   # Snowflake Workspace deployment
│   ├── pyproject.toml                  # Dependencies
│   └── .streamlit/config.toml          # Theme configuration
│
├── sql/                                # Snowflake SQL Objects
│   ├── guardrails_queries.sql          # 10 analytical queries
│   └── guardrails_infrastructure.sql   # Alerts, dynamic tables, views, tasks
│
├── tests/                              # Test Suite (50+ tests)
│   ├── conftest.py                     # Shared fixtures & data generators
│   ├── test_aisoc.py                   # 50 pytest unit tests
│   ├── test_scenarios.py              # 5 E2E scenario simulations
│   └── dummy_data.py                   # Test data utilities
│
├── docs/                               # Documentation & Reports
│   ├── guardrails_dashboard.html       # Premium HTML infographic
│   └── guardrails_analysis.ipynb       # Jupyter notebook analysis
│
├── .gitignore
├── LICENSE
├── CONTRIBUTING.md
└── README.md
```

---

## Quick Start

### Option 1: Snowflake Workspace (Recommended)

1. Upload `streamlit-app/` folder to a Snowflake Workspace
2. Click **Run** — the app starts in **Demo Mode** with 500 synthetic records
3. Toggle "Demo Mode" OFF in the sidebar to query live `ACCOUNT_USAGE` data

### Option 2: Deploy Infrastructure

```sql
-- Run in a Snowflake worksheet (update email addresses first)
-- Creates: alerts, dynamic tables, views, scheduled tasks
@sql/guardrails_infrastructure.sql
```

### Option 3: Run Tests Locally

```bash
pip install pandas numpy pytest
pytest tests/test_aisoc.py -v          # 50 unit tests
python tests/test_scenarios.py          # 5 E2E scenarios
```

---

## Dashboard Tabs

<details>
<summary><strong>1. Executive Summary</strong> — Composite risk score with recommendations</summary>

- Weighted risk score (0-100) combining flag rate, privileged access, velocity, off-hours
- Auto-generated severity-based recommendations
- Real-time incident feed with countdown timers
</details>

<details>
<summary><strong>2. Incidents</strong> — Auto-generated security incidents</summary>

- P1/P2 classification based on injection + privileged role + off-hours
- Visual timeline with color-coded severity
- Incident details with full request metadata
</details>

<details>
<summary><strong>3. UEBA</strong> — User & Entity Behavior Analytics</summary>

- Per-user behavioral profiling
- Night/weekend activity detection
- Token consumption anomalies (Z-score based)
</details>

<details>
<summary><strong>4. MITRE ATLAS</strong> — AI threat framework mapping</summary>

- Technique detection matrix
- Real-time counts per TTP
- Attack chain visualization
</details>

<details>
<summary><strong>5. Alerts</strong> — Velocity spikes & anomaly detection</summary>

- 8x/16x velocity threshold alerts
- Off-hours privilege escalation flags
- Multi-source correlation
</details>

<details>
<summary><strong>6. Drift</strong> — Period-over-period comparison</summary>

- Week-over-week delta indicators
- Source distribution shift detection
- Baseline deviation scoring
</details>

<details>
<summary><strong>7. Compliance</strong> — Regulatory control mapping</summary>

- 6 automated control checks (pass/fail)
- Mapped to: SOC 2, ISO 27001, NIST AI RMF, EU AI Act, GDPR, PCI DSS, HIPAA, FedRAMP
- Export-ready compliance attestation
</details>

<details>
<summary><strong>8. Cost Analytics</strong> — Credit consumption & forecasting</summary>

- Per-source chargeback allocation
- 7-day linear forecast projection
- Cache hit efficiency metrics
</details>

<details>
<summary><strong>9. Kill Switch</strong> — Emergency response commands</summary>

- Pre-built SQL for immediate incident containment
- Role revocation, network policy, account suspension
- One-click copy for rapid response
</details>

<details>
<summary><strong>10. Export</strong> — Data extraction & reporting</summary>

- CSV download of filtered data
- Compliance report generation
- SHA-256 integrity hash for audit trail
</details>

---

## Test Coverage

| Suite | Tests | Coverage |
|-------|-------|----------|
| Unit Tests | 50 | All analytics functions, edge cases, null handling |
| E2E Scenarios | 5 | Clean, Attack, Velocity Spike, Insider Threat, Drift |
| Edge Cases | ✓ | Empty data, single row, 100% flags, null JSON, large tokens |

### Test Scenarios

| Scenario | Description | Expected Outcome |
|----------|-------------|------------------|
| Clean Operations | 200 normal scans, business hours | Risk score < 20 |
| Active Attack | 25% flag rate, privileged roles | Risk score > 70, P1 incidents |
| Velocity Spike | 16x normal rate in 1 hour | Velocity alert triggered |
| Insider Threat | Admin at 3 AM, all flags | Max risk, UEBA anomaly |
| Drift Detection | 50% increase week-over-week | Drift indicators positive |

---

## Data Source

This project queries the Snowflake Account Usage view:

```sql
SNOWFLAKE.ACCOUNT_USAGE.CORTEX_AI_GUARDRAILS_USAGE_HISTORY
```

**Key columns:** `USER_NAME`, `AGENTIC_SOURCE`, `GUARDRAILS_SIGNAL`, `GUARDRAIL_RESULTS`, `TOKEN_CREDITS`, `TOKENS_GRANULAR`, `METADATA`

**Agentic sources tracked:**
- `CORTEX_CODE_CLI` | `CORTEX_CODE_DESKTOP` | `CORTEX_CODE_SNOWSIGHT`
- `CORTEX_AGENT` | `SNOWFLAKE_INTELLIGENCE`

---

## Requirements

- **Snowflake Account** with `ACCOUNTADMIN` or role with `ACCOUNT_USAGE` access
- **Snowflake Workspace** (for Streamlit deployment)
- **Python 3.11+** (for local testing)
- **Warehouse:** `COMPUTE_WH` (configurable in `snowflake.yml`)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

**Built for [Snowflake Quick Bytes](https://medium.com/@snowflakechronicles) by Satish Kumar**

[![Medium](https://img.shields.io/badge/Medium-@snowflakechronicles-000000?style=flat&logo=medium)](https://medium.com/@snowflakechronicles)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-satishkumar--snowflake-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/satishkumar-snowflake)
[![GitHub](https://img.shields.io/badge/GitHub-skrz2014-181717?style=flat&logo=github)](https://github.com/skrz2014)

</div>
