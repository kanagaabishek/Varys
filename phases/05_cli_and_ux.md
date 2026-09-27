# Phase 5: CLI & Live Trace UI

## 1. Goal & Objectives
Deliver a clean, high-impact terminal interface. When the user executes `$ varys "<question>"`, they should see the agent's thought process unfold in real-time (tool calls, arguments, returned snippets) before revealing a beautifully formatted diagnosis report card.

---

## 2. Terminal UI Design & Experience

### 1. Live Step-by-Step Investigation Trace
Using Python `rich.live.Live` and `rich.tree.Tree`, display each action as it happens:

```
$ varys "why is the payment-pipeline job unstable?"

🔎 [bold cyan]VARYS CI Intelligence Agent[/] — Initializing investigation...
Target Pipeline: [yellow]payment-pipeline[/]

  ├── ⚙️ [bold blue]Step 1: Inspecting Build History[/]
  │   └── 📞 Tool: get_recent_builds(job_name="payment-pipeline", count=20)
  │   └── 📊 Result: 20 builds analyzed, 6 failures detected (30% failure rate)
  │
  ├── ⚙️ [bold blue]Step 2: Inspecting Failed Test Executions[/]
  │   └── 📞 Tool: get_test_results(job_name="payment-pipeline", build_number=230)
  │   └── 📊 Result: 1 failed test: DatabaseConnectionTest (SocketTimeoutException)
  │
  ├── ⚙️ [bold blue]Step 3: Evaluating Test Flakiness Timeline[/]
  │   └── 📞 Tool: get_test_history(job_name="payment-pipeline", test_name="DatabaseConnectionTest", count=15)
  │   └── 📊 Result: Pass/Fail flip rate = 0.53 (Flaky pattern detected: P-F-P-P-F-P-F)
  │
  ├── ⚙️ [bold blue]Step 4: Correlating Commit Diffs[/]
  │   └── 📞 Tool: get_commits_between(job_name="payment-pipeline", start_build=215, end_build=217)
  │   └── 📊 Result: Commit db7a19f modified 'src/main/resources/application-db.yml'
  │
  └── ✨ [bold green]Investigation Complete (4 turns, 2.4s)[/]
```

### 2. Formatted Diagnosis Report Card

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     VARYS PIPELINE DIAGNOSIS REPORT                      ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

🚨 [bold red]CRITICAL ISSUE DETECTED:[/] Flaky Database Connection Failures

📌 [bold]Root Cause:[/]
Commit [bold cyan]db7a19f[/] ("chore(db): update hikari connection pool timeout and idle limits")
by [italic]alex.dev@corp.com[/] reduced connection acquisition timeouts from 10,000ms to 5,000ms,
triggering intermittent SocketTimeoutExceptions in [bold yellow]DatabaseConnectionTest[/].

📊 [bold]Key Evidence:[/]
  • Pipeline Failure Rate: Rose from 0% (Builds #201-#215) to 40% (Builds #216-#230)
  • Test Flakiness Score: 0.53 (Alternating pass/fail on identical code)
  • Primary Failing Test: io.jenkins.payment.db.DatabaseConnectionTest
  • Affected Builds: #217, #220, #222, #225, #228, #230

💡 [bold green]Recommended Actions:[/]
  1. Increase HikariCP `connection-timeout` in `application-db.yml` back to 10,000ms or tune test container DB pooling.
  2. Isolate `DatabaseConnectionTest` with an explicit testcontainer warmup hook.
```

---

## 3. Implementation Tasks

- [ ] **Task 5.1**: Build `varys/cli.py` using `typer` or `click` to handle command line arguments (`--model`, `--api-key`, `--db-path`, `--mock`, `--verbose`).
- [ ] **Task 5.2**: Build `varys/ui/console.py` and `varys/ui/renderer.py` using `rich` for live streaming tables, trees, and panels.
- [ ] **Task 5.3**: Add `--dry-run` or `--mock-llm` flag so the entire CLI demo can be run and tested without requiring an active internet connection or paid API key.
- [ ] **Task 5.4**: Add a summary export flag (`--export-json`, `--export-markdown`) for CI integration.

---

## 4. Verification Checklist & Success Criteria

1. Running `varys "why is payment-pipeline red?"` renders real-time colored step indicators with zero UI flicker.
2. The diagnosis box is clear, well-spaced, and fits standard 80-column and 120-column terminals.
3. If `--verbose` is enabled, full JSON tool payloads and LLM thought tokens are displayed.
