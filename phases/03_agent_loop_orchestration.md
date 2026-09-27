# Phase 3: Agent Loop & Reasoning Engine

## 1. Goal & Objectives
Build the core autonomous reasoning loop. The agent must dynamically plan its investigation, call tools based on findings, evaluate whether more evidence is needed, avoid redundant calls, and stop when it can deliver a high-confidence diagnosis.

---

## 2. ReAct Agent Loop State Machine

```
               ┌──────────────────────────────┐
               │    User Inquiry / Prompt     │
               └──────────────┬───────────────┘
                              │
                              ▼
               ┌──────────────────────────────┐
               │   Initialize Conversation    │
               │  - Inject System Prompt      │
               │  - Register 4 Tool Schemas   │
               │  - Set turn_count = 0        │
               └──────────────┬───────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           │
     ┌──────────────────────┐               │
     │  Call LLM with Tools │               │
     └──────────┬───────────┘               │
                │                           │
        ┌───────┴────────┐                  │
        ▼                ▼                  │
 [Tool Call(s)]   [Final Diagnosis]         │
        │                │                  │
        │                ▼                  │
        │         ┌──────────────┐          │
        │         │ Return Final │          │
        │         │ Output & End │          │
        │         └──────────────┘          │
        ▼                                   │
 ┌──────────────┐                           │
 │ Execute Tool │                           │
 │ via MCP/DAO  │                           │
 └──────┬───────┘                           │
        │                                   │
        ▼                                   │
 ┌──────────────┐                           │
 │ Append Result│                           │
 │  to Context  │                           │
 └──────┬───────┘                           │
        │                                   │
        ▼                                   │
 ┌──────────────┐                           │
 │ turn_count++ │                           │
 └──────┬───────┘                           │
        │                                   │
        ├───────── turn_count >= 5 ? ───────┤ (Force conclusion)
        │                 │                 │
        │ (No)            ▼ (Yes)           │
        └──────────> Send Synthesis Prompt ─┘
```

---

## 3. System Prompt Engineering

The system prompt enforces systematic CI debugging behavior:

```markdown
You are Varys, an expert CI/CD diagnostic intelligence agent specializing in Jenkins pipelines.
Your goal is to autonomously investigate pipeline failures, test flakiness, and duration regressions.

### Investigation Protocol:
1. **Initial Assessment**: Always start by checking recent build history using `get_recent_builds` to establish the baseline and failure/duration rate.
2. **Drill Down**:
   - If builds are FAILING: Inspect failing builds with `get_test_results`.
   - If specific tests fail intermittently: Check their historical pattern with `get_test_history` to verify if they are flaky vs constantly broken.
   - If failure/regression began at a specific point: Check commits between the last good build and first bad build with `get_commits_between`.
   - If builds are SLOWING DOWN: Compare durations across builds and check for infrastructure/dependency commits.
3. **Evidence-Driven Conclusion**:
   - Only conclude when you have correlated the symptom (e.g. flaky test or slow stage) with a candidate root cause (e.g. configuration or dependency commit).
   - If you have sufficient evidence, DO NOT make unnecessary tool calls. Formulate your final diagnosis.

### Output Requirements:
When you conclude, output a structured diagnosis with:
- **Summary of Problem**: What is happening (failure rate, duration increase, flaky tests).
- **Root Cause Analysis**: The specific test, step, or commit responsible.
- **Evidence Trail**: List of build numbers, error messages, and commit hashes confirming this.
- **Actionable Recommendation**: Specific steps for the developer to fix the issue.
```

---

## 4. Loop Safeguards & Error Handling

1. **Iteration Limit**: Hard cap at 5 turns. If turn 5 is reached without a diagnosis, the agent is prompted with: `"Iteration cap reached. Synthesize all collected evidence and output your final diagnosis immediately."`
2. **Tool Failure Resilience**: If a tool returns an error (e.g. invalid build number or missing test), the error message is fed back to the LLM so it can recover or refine its query without crashing.
3. **Deduplication Safeguard**: Prevents the agent from issuing the exact same tool call with identical parameters twice.

---

## 5. Implementation Tasks

- [ ] **Task 3.1**: Create `varys/agent/types.py` defining `AgentMessage`, `ToolCall`, `StepResult`, and `DiagnosisResult`.
- [ ] **Task 3.2**: Create `varys/agent/prompts.py` containing the system prompt and formatting templates.
- [ ] **Task 3.3**: Create `varys/agent/loop.py` implementing the async ReAct loop with multi-provider support (OpenAI / Anthropic / Gemini SDK or unified LiteLLM).
- [ ] **Task 3.4**: Write unit & integration tests in `tests/test_agent_loop.py` using a mock LLM client to ensure proper loop termination and context management.

---

## 6. Verification Checklist & Success Criteria

1. The agent loop successfully completes a multi-step investigation in <= 5 turns.
2. Tool execution results are accurately injected into conversation history.
3. If an iteration limit is reached, it yields a valid partial diagnosis rather than hanging.
4. Token usage and step logs are captured for observability.
