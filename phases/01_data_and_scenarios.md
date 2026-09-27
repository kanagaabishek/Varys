# Phase 1: Data Setup & Seed Scenarios

## 1. Goal & Objectives
Establish a zero-dependency, deterministic data storage layer and generator for CI test scenarios. This isolates the agent development from external Jenkins network flakes and ensures live demonstrations run flawlessly every single time.

---

## 2. SQLite Database Schema Design

A lightweight SQLite file (`varys.db`) storing realistic Jenkins pipelines, builds, test executions, and commit metadata.

```sql
-- 1. Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    name TEXT PRIMARY KEY,
    description TEXT,
    repository_url TEXT
);

-- 2. Builds table
CREATE TABLE IF NOT EXISTS builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    build_number INTEGER NOT NULL,
    result TEXT CHECK(result IN ('SUCCESS', 'FAILURE', 'UNSTABLE', 'ABORTED')),
    duration_sec REAL NOT NULL,
    timestamp TEXT NOT NULL,
    commit_hash TEXT NOT NULL,
    FOREIGN KEY(job_name) REFERENCES jobs(name),
    FOREIGN KEY(commit_hash) REFERENCES commits(commit_hash),
    UNIQUE(job_name, build_number)
);

-- 3. Test Results table
CREATE TABLE IF NOT EXISTS test_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name TEXT NOT NULL,
    build_number INTEGER NOT NULL,
    test_name TEXT NOT NULL,
    suite_name TEXT NOT NULL,
    status TEXT CHECK(status IN ('PASSED', 'FAILED', 'SKIPPED')),
    duration_sec REAL NOT NULL,
    error_message TEXT,
    stack_trace TEXT,
    FOREIGN KEY(job_name, build_number) REFERENCES builds(job_name, build_number)
);

-- 4. Commits table
CREATE TABLE IF NOT EXISTS commits (
    commit_hash TEXT PRIMARY KEY,
    job_name TEXT NOT NULL,
    author TEXT NOT NULL,
    message TEXT NOT NULL,
    files_changed TEXT NOT NULL, -- JSON array of strings, e.g. '["src/main/resources/application-db.yml"]'
    diff_summary TEXT,
    timestamp TEXT NOT NULL
);

-- Performance & Lookup Indexes
CREATE INDEX IF NOT EXISTS idx_builds_job_num ON builds(job_name, build_number);
CREATE INDEX IF NOT EXISTS idx_test_results_job_build ON test_results(job_name, build_number);
CREATE INDEX IF NOT EXISTS idx_test_results_lookup ON test_results(job_name, test_name, build_number);
```

### Commit Linking & `get_commits_between` Query Semantics
To ensure referential integrity, **every build maps to a valid non-null `commit_hash` with a corresponding row in `commits`**. 

Because `commits` stores git metadata while `builds` tracks pipeline execution, `get_commits_between(job_name, start_build, end_build)` is implemented via a direct join:

```sql
SELECT 
    c.commit_hash,
    c.job_name,
    c.author,
    c.message,
    c.files_changed,
    c.diff_summary,
    c.timestamp,
    b.build_number
FROM builds b
JOIN commits c ON b.commit_hash = c.commit_hash
WHERE b.job_name = :job_name 
  AND b.build_number BETWEEN :start_build AND :end_build
ORDER BY b.build_number ASC;
```

---

## 3. Seed Scenarios Specification

### Scenario A: Flaky Test + Database Config Regression
- **Job Name**: `payment-pipeline`
- **Builds**: Total 30 builds (`#201` to `#230`)
- **Other Tests in Suite (Always 100% PASSED)**: `PaymentIntegrationTest`, `RefundIntegrationTest`, `AuthTokenTest` (~1.2s each)
- **Commits Strategy**: Builds #201–#215 and #217–#230 point to routine functional commits (e.g. `"feat(pay): add idempotency header check"`, `"refactor(api): clean up refund DTO"` modifying Java files).
- **Trigger Commit (Build #216)**:
  - `commit_hash="db7a19f"`
  - `author="alex.dev@corp.com"`
  - `message="chore(db): update hikari connection pool timeout and idle limits"`
  - `files_changed='["src/main/resources/application-db.yml"]'`
  - `diff_summary="1 file changed, 4 insertions(+), 2 deletions(-)"`
- **Complete Test Matrix for `DatabaseConnectionTest` (Builds #201–#230)**:
  - **Healthy Baseline (#201–#215, 100% PASS)**:
    - `#201` to `#215`: `PASSED` (duration: 0.8s–1.1s)
  - **Trigger Build (#216, PASS)**:
    - `#216`: `PASSED` (duration: 1.0s)
  - **Flaky Regression (#217–#230, 6 FAILURES, 8 PASSES)**:
    - `#217`: **FAILED** (`SocketTimeoutException: Connection acquisition timeout after 5000ms`, duration: 5.1s)
    - `#218`: `PASSED` (duration: 1.1s)
    - `#219`: `PASSED` (duration: 1.2s)
    - `#220`: **FAILED** (`SocketTimeoutException: Connection acquisition timeout after 5000ms`, duration: 5.2s)
    - `#221`: `PASSED` (duration: 1.0s)
    - `#222`: **FAILED** (`SocketTimeoutException: Connection acquisition timeout after 5000ms`, duration: 5.0s)
    - `#223`: `PASSED` (duration: 1.1s)
    - `#224`: `PASSED` (duration: 1.2s)
    - `#225`: **FAILED** (`SocketTimeoutException: Connection acquisition timeout after 5000ms`, duration: 5.1s)
    - `#226`: `PASSED` (duration: 1.0s)
    - `#227`: `PASSED` (duration: 1.1s)
    - `#228`: **FAILED** (`SocketTimeoutException: Connection acquisition timeout after 5000ms`, duration: 5.2s)
    - `#229`: `PASSED` (duration: 1.2s)
    - `#230`: **FAILED** (`SocketTimeoutException: Connection acquisition timeout after 5000ms`, duration: 5.1s)
- **Pipeline Build Results for `payment-pipeline`**:
  - `#201`–`#215`: `SUCCESS` (duration: 420s–460s)
  - `#216`: `SUCCESS` (duration: 435s)
  - `#217`: `FAILURE` (duration: 475s)
  - `#218`, `#219`: `SUCCESS`
  - `#220`: `FAILURE`
  - `#221`: `SUCCESS`
  - `#222`: `FAILURE`
  - `#223`, `#224`: `SUCCESS`
  - `#225`: `FAILURE`
  - `#226`, `#227`: `SUCCESS`
  - `#228`: `FAILURE`
  - `#229`: `SUCCESS`
  - `#230`: `FAILURE`

---

### Scenario B: Silent Duration / Build-Time Regression
- **Job Name**: `order-service-build`
- **Builds**: Total 25 builds (`#101` to `#125`)
- **Outcome**: All builds pass (`result="SUCCESS"`), but duration balloons from ~4 minutes to ~18 minutes.
- **Tests**: `OrderFlowTest`, `InventorySyncTest` (all builds `PASSED` in ~45s total).
- **Commits Strategy**: Builds #101–#109 and #111–#125 point to routine commits (e.g. `"feat(order): add cart item validation"`, `"fix: handling zero quantity orders"`).
- **Trigger Commit (Build #110)**:
  - `commit_hash="a1f89c0"`
  - `author="ci-ops@corp.com"`
  - `message="build(gradle): add full container image scan step to pipeline"`
  - `files_changed='["Jenkinsfile", "build.gradle.kts"]'`
  - `diff_summary="2 files changed, 28 insertions(+), 2 deletions(-)"`
- **Build Duration Timeline (`order-service-build`)**:
  - `#101`–`#109`: 240s–260s (~4 mins)
  - `#110`: 780s (Spike to 13 mins with introduction of image scan)
  - `#111`–`#125`: 950s–1080s (16–18 mins as image layers accumulate without Docker caching)

---

## 4. Implementation Steps & Tasks

- [x] **Task 1.1**: Create `varys/storage/database.py` implementing the SQLite schema with table creation, indices, and typed queries (including the `get_commits_between` JOIN query).
- [x] **Task 1.2**: Create `varys/storage/seed.py` that:
  - Inserts the job rows (`payment-pipeline` and `order-service-build`) into `jobs` table first.
  - Generates realistic `commits` for all builds (routine commits for non-trigger builds, exact trigger commits `db7a19f` and `a1f89c0`).
  - Populates `builds` and `test_results` tables strictly adhering to the complete matrices of Scenario A and Scenario B.
- [x] **Task 1.3**: Add a CLI command `python -m varys.storage.seed --reset` that deletes existing `varys.db` and reseeds all records in < 1 second.
- [x] **Task 1.4**: Write unit tests in `tests/test_scenarios.py` verifying data consistency for both Scenario A and Scenario B.

---

## 5. Verification Checklist & Success Criteria

Execute: `python -m varys.storage.seed --reset` followed by `pytest tests/test_scenarios.py`:

1. **Database Creation**: `varys.db` is created with all tables and indices.
2. **Jobs Verification**: `jobs` table contains both `payment-pipeline` and `order-service-build`.
3. **Scenario A Verification**:
   - Querying `get_recent_builds("payment-pipeline", 30)` returns 30 builds with exactly 6 `FAILURE` results (#217, #220, #222, #225, #228, #230) and 24 `SUCCESS` results.
   - Querying `get_test_history("payment-pipeline", "DatabaseConnectionTest", 15)` returns the exact pass/fail sequence with 6 failures and 9 passes.
   - Querying `get_commits_between("payment-pipeline", 215, 217)` returns trigger commit `db7a19f` modifying `application-db.yml`.
4. **Scenario B Verification**:
   - Querying `get_recent_builds("order-service-build", 25)` returns 25 builds (all `SUCCESS`), with durations jumping from ~250s (builds #101–#109) to 780s at #110 and >950s for builds #111–#125.
   - Querying `get_commits_between("order-service-build", 108, 112)` returns trigger commit `a1f89c0` modifying `Jenkinsfile` and `build.gradle.kts`.
   - All tests for `order-service-build` report `status="PASSED"`.
