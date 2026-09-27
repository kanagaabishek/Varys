# Phase 6: End-to-End Verification & Interview Guide

## 1. Goal & Objectives
Ensure the entire Varys project is 100% reliable for live interview demonstrations, backed by automated end-to-end regression tests, and equipped with sharp answers to technical questions.

---

## 2. Automated E2E Verification Suite

We will create automated evaluation scripts that benchmark the agent's diagnostic accuracy against ground truth scenarios:

```python
# tests/test_e2e_evaluation.py

def test_scenario_a_diagnosis_accuracy():
    """Verify Varys correctly identifies DatabaseConnectionTest and commit db7a19f."""
    agent = VarysAgent(db_path="varys.db")
    result = agent.run("Why is payment-pipeline unstable?")
    
    assert "DatabaseConnectionTest" in result.diagnosis
    assert "db7a19f" in result.diagnosis or "hikari" in result.diagnosis.lower()
    assert result.step_count <= 5

def test_scenario_b_duration_regression():
    """Verify Varys identifies container image scan step in build.gradle.kts / Jenkinsfile."""
    agent = VarysAgent(db_path="varys.db")
    result = agent.run("Why is order-service-build taking so long recently?")
    
    assert "duration" in result.diagnosis.lower() or "slow" in result.diagnosis.lower()
    assert "a1f89c0" in result.diagnosis or "image scan" in result.diagnosis.lower()
    assert result.step_count <= 5
```

---

## 3. Live Demo Script (2-Minute Pitch)

1. **The Problem Setup (15s)**:
   > "In large CI systems like Jenkins, engineers spend hours scrolling through build logs and guessing if a test failed because of their code or because the test is flaky. Simple LLM wrappers make a single call and often hallucinate."
2. **The Demo Action (30s)**:
   > "Here is Varys. I ask: `varys 'why is the payment-pipeline job unstable?'`. Watch the live reasoning loop."
3. **Explaining the Steps (45s)**:
   - "Step 1: Notice Varys checks build history first to quantify the failure rate."
   - "Step 2: It isolates the failed builds and discovers `DatabaseConnectionTest`."
   - "Step 3: Instead of concluding immediately, it calls `get_test_history` and calculates an alternation flip rate of 0.53, identifying it as flaky."
   - "Step 4: It correlates the failure onset to commit `db7a19f`, which changed database pool timeouts."
4. **The Value (30s)**:
   > "Within 3 seconds and 4 tool turns, Varys delivered a high-confidence, evidence-backed diagnosis that saved hours of manual triage."

---

## 4. Technical Interview Defense Guide

### Q1: Why did you use a multi-step tool-use loop instead of a single prompt with all context?
> **Answer**: CI pipelines generate massive amounts of log and metadata. Dumping 30 builds of logs into a single prompt blows up context windows, increases cost, and introduces hallucination. The ReAct agent loop allows the agent to start with high-level build summaries and autonomously drill down into specific tests and commits only when the evidence warrants it.

### Q2: Why did you use seeded data instead of requiring a live Jenkins instance?
> **Answer**: In a live interview demo or CI test suite, relying on live infrastructure introduces external network latency, auth overhead, and non-deterministic flakes. By designing seeded SQLite scenarios that mimic real-world Jenkins API responses, we ensure 100% deterministic, sub-second demos while focusing our engineering effort on the agent reasoning and tool orchestration layers.

### Q3: What prevents the agent from entering an infinite loop or burning API credits?
> **Answer**: Three layers of defense:
> 1. A hard iteration cap (max 5 turns).
> 2. Deduplication filters that reject duplicate tool calls with identical parameters.
> 3. An automatic synthesis prompt triggered at turn 5 to force a conclusion based on available evidence.

### Q4: How does your flakiness detection work?
> **Answer**: It uses a state-transition flip rate heuristic: $\rho = \frac{\text{flips}}{N - 1}$ combined with failure rate entropy. A genuinely broken test transitions from PASS to FAIL once and stays FAIL ($\rho \approx 0$). A flaky test flips back and forth repeatedly ($\rho \ge 0.25$).

---

## 5. Verification Checklist & Success Criteria

1. Both Scenario A and Scenario B pass `pytest tests/test_e2e_evaluation.py`.
2. Clean `README.md` and CLI `--help` ready for presentation.
3. 2-minute demo can be executed offline using `--mock-llm` if Wi-Fi is unavailable.
