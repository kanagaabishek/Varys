# Varys — Autonomous Jenkins CI Intelligence & Diagnostic Agent

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://python.org)
[![Architecture](https://img.shields.io/badge/Architecture-ReAct%20Loop%20%2B%20MCP-purple.svg)]()
[![Protocol](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-orange.svg)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> *"A spider has many little whisperers."*  
> **Varys** is an autonomous AI diagnostic agent that investigates Jenkins CI pipeline failures, flakiness, and performance regressions. Instead of blindly dumping massive log files into a prompt, Varys employs an interactive **ReAct (Reasoning + Acting) loop** over **Model Context Protocol (MCP)** tools to systematically interrogate build telemetry, test pass/fail state transitions, and git commit diffs.

---

## Table of Contents
1. [Executive Summary & Problem Statement](#1-executive-summary--problem-statement)
2. [System Architecture](#2-system-architecture)
3. [Key Engineering Decisions & Trade-Offs](#3-key-engineering-decisions--trade-offs)
4. [Mathematical Heuristics](#4-mathematical-heuristics)
5. [Quickstart & Live Execution](#5-quickstart--live-execution)
6. [Real-World Jenkins & GitHub Integration](#6-real-world-jenkins--github-integration)
7. [Deterministic Scenarios & Benchmark Suite](#7-deterministic-scenarios--benchmark-suite)
8. [Production Reliability & Guardrails](#8-production-reliability--guardrails)
9. [Authors & Contributors](#authors--contributors)

---

## 1. Executive Summary & Problem Statement

### The Problem
* **Log Overload & Triage Fatigue**: Modern microservice CI pipelines generate megabytes of console output per build. On average, developers spend 20–40 minutes per failure distinguishing between genuine regressions and transient flakes.
* **The Failure of Naive Single-Shot LLMs**: Pasting raw Jenkins logs into standard LLMs fails because:
  1. It exceeds context limits or introduces token cost inefficiency ($0.20+ per triage).
  2. It lacks cross-build temporal context (e.g. *Did this test fail yesterday? When did the duration spike begin?*).
  3. LLMs hallucinate root causes without verifying the underlying Git diff or test history.

### The Solution: Varys
Varys acts like a senior Site Reliability Engineer:
* **Hypothesis-Driven**: Starts with high-level pipeline history, isolates anomalies, tests hypotheses against test transition histories, and correlates changes to specific commit authors and configuration diffs.
* **Deterministic Tool Protocol**: Interacts exclusively with standardized **MCP (Model Context Protocol)** tools with strict Pydantic schemas.
* **Blazing Fast**: Reaches root-cause attribution within **3 to 4 turns (< 5 seconds)** with full evidence citations.

---

## 2. System Architecture

```
                                  ┌────────────────────────────────────────┐
                                  │             User / CLI / CI            │
                                  │  $ varys "why is payment-pipeline red?"│
                                  └──────────────────┬─────────────────────┘
                                                     │
                                                     ▼
                                  ┌────────────────────────────────────────┐
                                  │         Varys Agent Orchestrator       │
                                  │  - ReAct Multi-Turn Engine             │
                                  │  - Context Window Budgeting            │
                                  │  - Loop Safeguards (Max 5 Turns)       │
                                  └──────────────────┬─────────────────────┘
                                                     │ JSON-RPC (MCP)
                                                     ▼
                                  ┌────────────────────────────────────────┐
                                  │          Varys MCP Tool Server         │
                                  │                                        │
                                  │  [1] get_recent_builds(job, count)     │
                                  │  [2] get_test_results(job, build_num)  │
                                  │  [3] get_test_history(job, test, count)│
                                  │  [4] get_commits_between(b_a, b_b)     │
                                  └──────────────────┬─────────────────────┘
                                                     │
                             ┌───────────────────────┴───────────────────────┐
                             ▼                                               ▼
                ┌─────────────────────────┐                     ┌─────────────────────────┐
                │   SQLite Scenario DB    │                     │   Live CI/CD Adapters   │
                │  - Zero-latency fixtures│                     │  - Jenkins REST API     │
                │  - Regression benchmarks│                     │  - GitHub Commits / PRs │
                └─────────────────────────┘                     └─────────────────────────┘
```

### Core MCP Tool Contracts

| Tool | Parameters | Output Schema | Purpose |
|---|---|---|---|
| `get_recent_builds` | `job_name: str`, `count: int` | `List[BuildSummary]` | Snapshot of recent build statuses, durations, and timestamps |
| `get_test_results` | `job_name: str`, `build_number: int` | `List[TestResultItem]` | Individual test execution details, assertion errors, and stack traces |
| `get_test_history` | `job_name: str`, `test_name: str`, `count: int` | `List[TestHistoryItem]` | Temporal status trajectory across builds for flakiness evaluation |
| `get_commits_between` | `job_name: str`, `start_build: int`, `end_build: int` | `List[CommitItem]` | Git author, message, changed files, and diff stats between builds |

---

## 3. Key Engineering Decisions & Trade-Offs

### 1. Multi-Turn ReAct Loop vs. Single-Shot RAG
* **Decision**: Multi-turn ReAct with autonomous tool selection.
* **Trade-off**: Requires multiple LLM API roundtrips (~2-4 seconds total).
* **Rationale**: Pipeline diagnosis is inherently iterative. An engineer cannot know which test history or commit diff to inspect until after querying the build summary. Fetching *everything* upfront (all logs, all tests, all diffs) would consume >150k tokens per prompt. ReAct uses <4k total tokens across the entire session.

### 2. Model Context Protocol (MCP) as First-Class Tool Interface
* **Decision**: Expose all Jenkins and Git interactions via standard MCP tool endpoints.
* **Rationale**: MCP decouples the LLM provider from the telemetry source. Varys can be embedded directly into Claude Desktop, Cursor, IDE extensions, or custom CLI runners without rewriting tool schemas or security layers.

### 3. Dual Mode: Seeded Local Testbed vs. Live REST Provider
* **Decision**: Backed by a deterministic SQLite database with an optional live ingestion bridge.
* **Rationale**: Live CI environments are flaky, rate-limited, and slow during CI testing or live interviews. The SQLite layer allows 100% deterministic, offline evaluation benchmarks (`pytest`), while `sync_live_jenkins.py` enables seamless deployment to production Jenkins masters.

---

## 4. Mathematical Heuristics

### A. Flakiness State-Transition Entropy Heuristic ($\rho$)
A naive failure rate ($\frac{\text{fails}}{\text{total}}$) fails to differentiate between a **broken test** (fails consistently after a bug) and a **flaky test** (intermittent non-deterministic failures). Varys computes the **Flip Rate**:

$$\rho = \frac{1}{N - 1} \sum_{i=1}^{N-1} \mathbb{I}(s_i \neq s_{i+1})$$

Where $s_i \in \{\text{PASS}, \text{FAIL}\}$ is the outcome at build $i$:
* **Consistently Broken Test**: `[PASS, PASS, PASS, FAIL, FAIL, FAIL]` $\implies \rho = \frac{1}{5} = 0.20$ (Single transition point).
* **Flaky Test**: `[PASS, FAIL, PASS, FAIL, PASS, FAIL]` $\implies \rho = \frac{5}{5} = 1.00$ (High entropy).
* **Threshold**: Any test with $\rho \ge 0.25$ and at least one pass + one fail is categorized as **FLAKY** with root cause mapped to environmental/async timing issues rather than code breakage.

### B. Duration Change-Point Detection
Varys flags pipeline regressions when the rolling duration step change exceeds:

$$\Delta D = \text{mean}(D_{\text{recent}}) - \text{mean}(D_{\text{baseline}}) > 2.5 \cdot \sigma(D_{\text{baseline}})$$

---

## 5. Quickstart & Live Execution

### Installation
```bash
# Clone the repository
git clone https://github.com/your-org/varys.git
cd varys

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### Environment Configuration
Create a `.env` file in the project root:
```env
GEMINI_API_KEY="your-gemini-api-key"
# Optional for live Jenkins/GitHub sync:
JENKINS_URL="http://localhost:8080"
JENKINS_USER="admin"
JENKINS_API_TOKEN="your-jenkins-token"
GITHUB_TOKEN="ghp_your-github-token"
```

### Running Investigations

#### 1. Live LLM Mode (Gemini 2.5 Flash)
```bash
python -m varys.cli "why is the payment-pipeline job unstable?"
```

#### 2. Offline / Deterministic Mock Mode (No API key needed)
```bash
python -m varys.cli "why is order-service-build taking so long recently?" --mock
```

#### Terminal Trace Output Preview:
```text
🔎 VARYS CI Intelligence Agent — Initializing investigation...
Question: "why is the payment-pipeline job unstable?"

  ├── ⚙️ Step 1: Check recent build status to find failed builds
  │   └── 📞 MCP Call: get_recent_builds(job_name='payment-pipeline', count=10)
  │   └── ↳ Result: 10 builds retrieved. Failed/Unstable: [#105, #103, #102]
  ├── ⚙️ Step 2: Inspect test failures in failed build #105
  │   └── 📞 MCP Call: get_test_results(job_name='payment-pipeline', build_number=105)
  │   └── ↳ Result: 1 failed: DatabaseConnectionTest.test_connection_pool_under_load
  ├── ⚙️ Step 3: Check execution history of DatabaseConnectionTest
  │   └── 📞 MCP Call: get_test_history(job_name='payment-pipeline', test_name='DatabaseConnectionTest...')
  │   └── ↳ Result: 10 runs: 4 PASSED, 6 FAILED. Flip rate: 0.56 (FLAKY)
  ├── ⚙️ Step 4: Check commits introduced around build #101-#102
  │   └── 📞 MCP Call: get_commits_between(job_name='payment-pipeline', start_build=101, end_build=102)
  │   └── ↳ Result: Commit db7a19f by dev-alex: "chore: tune db connection pool timeout"

╭────────────────────────── 🕵️ VARYS PIPELINE DIAGNOSIS REPORT ──────────────────────────╮
│                                                                                         │
│  ## 🚨 Root Cause Summary                                                               │
│  The `payment-pipeline` instability is driven by **flakiness in DatabaseConnectionTest**│
│  triggered by connection timeout adjustments introduced in commit `db7a19f`.           │
│                                                                                         │
│  ### 📊 Telemetry & Evidence                                                           │
│  - **Test Failure**: `DatabaseConnectionTest.test_connection_pool_under_load`           │
│  - **Flakiness Factor**: 56% alternation flip-rate across last 10 builds               │
│  - **Causal Commit**: `db7a19f` ("chore: tune db connection pool timeout")             │
│  - **Suspect Files**: `src/main/resources/application.yml`                             │
│                                                                                         │
│  ### 💡 Recommended Fix                                                                │
│  1. Revert the HikariCP connection timeout reduction in `application.yml`.             │
│  2. Add retry backoff for integration tests touching shared DB pools.                  │
╰─────────────────────────────────────────────────────────────────────────────────────────╯
```

---

## 6. Real-World Jenkins & GitHub Integration

Varys supports bi-directional synchronization with production CI/CD stacks:

### Syncing Live Production Data
To pull real build summaries, JUnit test reports, and GitHub commit diffs into Varys:
```bash
python scripts/sync_live_jenkins.py <JENKINS_JOB_NAME> <GITHUB_OWNER/REPO>
```

### Running Varys in Jenkinsfile Post-Actions
Automatically diagnose PR build failures and post comments to GitHub:
```groovy
post {
    failure {
        script {
            withCredentials([string(credentialsId: 'GEMINI_API_KEY', variable: 'GEMINI_API_KEY'),
                             string(credentialsId: 'GITHUB_TOKEN', variable: 'GITHUB_TOKEN')]) {
                sh '''
                    pip install -e varys/
                    python -m varys.cli "diagnose failure in build ${BUILD_NUMBER}" --format=json > diagnosis.json
                '''
            }
        }
    }
}
```

---

## 7. Deterministic Scenarios & Benchmark Suite

Varys includes reproducible real-world incident scenarios:

| Scenario | Job Name | Primary Pattern | Root Cause / Culprit |
|---|---|---|---|
| **Scenario A** | `payment-pipeline` | Flaky Test + Config Change | `DatabaseConnectionTest` flip-rate 0.56 caused by commit `db7a19f` |
| **Scenario B** | `order-service-build` | Step Duration Regression | Build duration doubled (180s $\to$ 420s) due to container vulnerability scan added in commit `a1f89c0` |

### Running Test Suite
```bash
pytest tests/ -v
```
* `tests/test_scenarios.py`: Validates database seed integrity and baseline data contracts.
* `tests/test_mcp_tools.py`: Unit tests for all 4 MCP tool endpoints.
* `tests/test_mcp_client.py`: Async MCP client-server loop validation.

---

## 8. Production Reliability & Guardrails

To prevent infinite loops, hallucination, and excessive API credit consumption, Varys enforces:
1. **Hard Turn Capping**: Maximum of 5 ReAct iterations per query.
2. **Tool Call Deduplication**: Automatically blocks repeated tool invocations with identical parameters.
3. **Graceful Synthesis Fallback**: If max turns are reached, the agent triggers a forced synthesis prompt using accumulated evidence rather than crashing.
4. **Offline Mock Mode**: Enables full test execution and offline demonstrations without external API dependencies.

---

## Authors & Contributors
* Built with ❤️ by the **Kanaga Abishek**.
