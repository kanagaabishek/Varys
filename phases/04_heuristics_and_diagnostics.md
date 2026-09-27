# Phase 4: Heuristics & Correlation Layer

## 1. Goal & Objectives
Equip Varys with robust, deterministic heuristics for test flakiness, duration change-points, and commit attribution. These algorithmic helpers enrich the raw tool outputs and provide mathematical ground truth that the agent can quote with confidence during interviews and diagnostics.

---

## 2. Core Heuristics Specifications

### 1. Test Flakiness Score (Pass/Fail Alternation & Flip Rate)
- **Problem**: Distinguishing between a genuinely broken test (100% fail after a commit) vs a flaky/nondeterministic test (alternating pass and fail on identical or nearby commits).
- **Algorithm (`flip_rate` & `failure_entropy`)**:
  - Let $S = [s_1, s_2, \dots, s_N]$ be the chronological statuses of a test ($s_i \in \{0, 1\}$ where $1 = \text{FAIL}, 0 = \text{PASS}$).
  - **Flip Count ($F$)**: Total number of transitions where $s_{i} \neq s_{i-1}$.
  - **Flip Rate ($\rho$)**: $\rho = \frac{F}{N - 1}$.
  - **Failure Rate ($p$)**: $p = \frac{\sum s_i}{N}$.
  - **Flakiness Classification**:
    - If $\rho \ge 0.25$ and $0.15 \le p \le 0.85$ $\rightarrow$ **FLAKY** (High confidence).
    - If $p = 1.0$ and $\rho = 0.0$ $\rightarrow$ **PERMANENT_BREAKAGE** (Deterministic regression).
    - If $p = 0.0$ $\rightarrow$ **HEALTHY**.

### 2. Pipeline Duration Change-Point & Regression Detection
- **Problem**: Detecting when build times jumped significantly without relying on brittle fixed thresholds.
- **Algorithm (Sliding Window Delta)**:
  - Divide recent builds into Baseline Window $W_{\text{base}}$ (e.g. builds 1–10) and Recent Window $W_{\text{recent}}$ (e.g. builds 11–20).
  - Compute Mean Duration $\mu_{\text{base}}$ and $\mu_{\text{recent}}$.
  - Compute Standard Deviation $\sigma_{\text{base}}$.
  - **Z-Score Regression**: $Z = \frac{\mu_{\text{recent}} - \mu_{\text{base}}}{\sigma_{\text{base}} + \epsilon}$.
  - If $Z > 3.0$ and $\frac{\mu_{\text{recent}}}{\mu_{\text{base}}} > 1.4$ $\rightarrow$ **REGRESSION DETECTED** (e.g., +40% spike).
  - Locate the exact change-point build $B_{\text{change}}$ where the duration first exceeded $\mu_{\text{base}} + 2\sigma_{\text{base}}$.

### 3. Commit Attribution & File Affinity Mapper
- **Problem**: Linking the regression build to the most probable culprit commit.
- **Heuristic**:
  - Inspect `files_changed` for all commits between $B_{\text{baseline}}$ and $B_{\text{change}}$.
  - Score file patterns:
    - High affinity for DB failures: `*.yml`, `*.properties`, `*database*`, `*pool*`, `*datasource*`.
    - High affinity for build regressions: `Jenkinsfile`, `*.gradle*`, `pom.xml`, `Dockerfile`, `docker-compose*`.
    - High affinity for test failures: `*Test.java`, `*Spec.groovy`, `*test*.py`.

---

## 3. Implementation Tasks

- [ ] **Task 4.1**: Implement `varys/heuristics/flakiness.py` with `calculate_flakiness_score(history: list[dict]) -> FlakinessReport`.
- [ ] **Task 4.2**: Implement `varys/heuristics/regressions.py` with `detect_duration_changepoint(builds: list[dict]) -> RegressionReport`.
- [ ] **Task 4.3**: Implement `varys/heuristics/commit_correlator.py` for keyword and file pattern scoring.
- [ ] **Task 4.4**: Integrate heuristics directly into the MCP tools and prompt helpers.
- [ ] **Task 4.5**: Write unit tests in `tests/test_heuristics.py` with known input sequences.

---

## 4. Verification Checklist & Success Criteria

1. Alternating sequence `[P, F, P, F, P, F]` yields classification `FLAKY` with flip rate $\rho = 1.0$.
2. Constant failure sequence `[P, P, F, F, F, F]` yields `PERMANENT_BREAKAGE` with change-point identified at index 2.
3. Scenario B duration jump from 250s to 800s triggers regression alert with exact culprit build.
