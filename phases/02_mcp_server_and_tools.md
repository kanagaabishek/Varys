# Phase 2: MCP Server & Tool Contracts

## 1. Goal & Objectives
Expose the 4 clean, strictly-typed Model Context Protocol (MCP) tools that the agent will call during its investigation. Ensure tool definitions are minimal, unambiguous, and adhere to the zero-scope-creep contract (no auth/pagination/write clutter).

---

## 2. MCP Tools Specification

### Tool 1: `get_recent_builds`
- **Description**: Retrieves summary metadata of the most recent N builds for a given Jenkins job.
- **Parameters**:
  - `job_name` (`string`, required): Name of the Jenkins job/pipeline (e.g. `"payment-pipeline"`).
  - `count` (`integer`, optional, default=15): Number of recent builds to retrieve.
- **Return Type**:
  ```json
  [
    {
      "build_number": 230,
      "result": "FAILURE",
      "duration_sec": 485.2,
      "timestamp": "2026-09-27T08:15:00Z",
      "commit_hash": "e98a12c"
    }
  ]
  ```

### Tool 2: `get_test_results`
- **Description**: Returns execution details and error traces for all test cases run in a specific build.
- **Parameters**:
  - `job_name` (`string`, required): Name of the job.
  - `build_number` (`integer`, required): The build number.
- **Return Type**:
  ```json
  [
    {
      "test_name": "DatabaseConnectionTest",
      "suite_name": "io.jenkins.payment.db",
      "status": "FAILED",
      "duration_sec": 12.4,
      "error_message": "SocketTimeoutException: Connection acquisition timeout after 5000ms"
    }
  ]
  ```

### Tool 3: `get_test_history`
- **Description**: Traces the pass/fail/skipped timeline of a single test across previous builds to diagnose flakiness or permanent breakage.
- **Parameters**:
  - `job_name` (`string`, required): Name of the job.
  - `test_name` (`string`, required): Fully qualified or simple name of the test.
  - `count` (`integer`, optional, default=15): Number of builds to trace back.
- **Return Type**:
  ```json
  [
    { "build_number": 230, "status": "FAILED", "duration_sec": 12.4 },
    { "build_number": 229, "status": "PASSED", "duration_sec": 1.2 },
    { "build_number": 228, "status": "FAILED", "duration_sec": 12.1 }
  ]
  ```

### Tool 4: `get_commits_between`
- **Description**: Fetches git commit metadata and changed file lists between two build numbers.
- **Parameters**:
  - `job_name` (`string`, required): Name of the job.
  - `start_build` (`integer`, required): Baseline healthy build number.
  - `end_build` (`integer`, required): Regression or failing build number.
- **Return Type**:
  ```json
  [
    {
      "commit_hash": "db7a19f",
      "author": "alex.dev@corp.com",
      "message": "chore(db): update hikari connection pool timeout and idle limits",
      "files_changed": ["src/main/resources/application-db.yml"],
      "diff_summary": "1 file changed, 4 insertions(+), 2 deletions(-)",
      "timestamp": "2026-09-25T14:20:00Z"
    }
  ]
  ```

---

## 3. Server Architecture

We will implement two ways to access these tools:
1. **Direct In-Memory Dispatcher**: Directly callable Python methods for blazing fast CLI execution.
2. **Standard MCP Server Interface (Stdio/SSE)**: Standard compliant MCP server using the official `mcp` library / `FastMCP` so it can also be inspected via external MCP inspectors (e.g. Claude Desktop, AGY IDE, or MCP Inspector).

```
varys/mcp/
├── __init__.py
├── server.py       # FastMCP server registration
└── tools.py        # Core tool implementations querying varys.storage.database
```

---

## 4. Implementation Tasks

- [ ] **Task 2.1**: Implement `varys/mcp/tools.py` with typed Pydantic models for inputs and outputs.
- [ ] **Task 2.2**: Integrate tools with `varys/storage/database.py` DAO.
- [ ] **Task 2.3**: Implement `varys/mcp/server.py` exposing the tools via FastMCP.
- [ ] **Task 2.4**: Implement tool invocation unit tests in `tests/test_mcp_tools.py` verifying response schema and error handling when invalid job or build IDs are passed.

---

## 5. Verification Checklist & Success Criteria

1. Running `pytest tests/test_mcp_tools.py` passes 100% with no warnings.
2. `get_test_history` gracefully returns an empty list if a test does not exist.
3. `get_commits_between` handles descending/ascending build ranges correctly (`start_build <= end_build`).
4. JSON serialization is strictly standard compliant.
