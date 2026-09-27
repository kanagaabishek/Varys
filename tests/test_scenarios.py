"""Unit tests for Varys database and seeded scenarios (Scenario A & B)."""

import pytest
from varys.storage.database import VarysDatabase
from varys.storage.seed import seed_all


@pytest.fixture
def db(tmp_path):
    """Creates a fresh, seeded SQLite database in a temporary directory."""
    db_file = tmp_path / "test_varys.db"
    return seed_all(db_path=db_file, reset=True)


def test_jobs_table_populated(db: VarysDatabase):
    """Verify jobs table contains both expected jobs."""
    jobs = db.get_all_jobs()
    job_names = [j["name"] for j in jobs]
    assert "payment-pipeline" in job_names
    assert "order-service-build" in job_names


def test_scenario_a_build_counts_and_failures(db: VarysDatabase):
    """Verify Scenario A has 30 builds with exactly 6 failures and 24 successes."""
    builds = db.get_recent_builds("payment-pipeline", count=50)
    assert len(builds) == 30

    failures = [b for b in builds if b["result"] == "FAILURE"]
    successes = [b for b in builds if b["result"] == "SUCCESS"]

    assert len(failures) == 6
    assert len(successes) == 24

    failed_build_nums = {b["build_number"] for b in failures}
    assert failed_build_nums == {217, 220, 222, 225, 228, 230}


def test_scenario_a_test_history_flakiness(db: VarysDatabase):
    """Verify DatabaseConnectionTest exhibits the exact alternating pass/fail pattern."""
    history = db.get_test_history("payment-pipeline", "DatabaseConnectionTest", count=30)
    assert len(history) == 30

    # Map build_number -> status
    status_by_build = {h["build_number"]: h["status"] for h in history}

    # Baseline builds 201-215 are all PASSED
    for b in range(201, 216):
        assert status_by_build[b] == "PASSED"

    # Trigger build 216 is PASSED
    assert status_by_build[216] == "PASSED"

    # Flaky period 217-230
    assert status_by_build[217] == "FAILED"
    assert status_by_build[218] == "PASSED"
    assert status_by_build[219] == "PASSED"
    assert status_by_build[220] == "FAILED"
    assert status_by_build[221] == "PASSED"
    assert status_by_build[222] == "FAILED"
    assert status_by_build[223] == "PASSED"
    assert status_by_build[224] == "PASSED"
    assert status_by_build[225] == "FAILED"
    assert status_by_build[226] == "PASSED"
    assert status_by_build[227] == "PASSED"
    assert status_by_build[228] == "FAILED"
    assert status_by_build[229] == "PASSED"
    assert status_by_build[230] == "FAILED"


def test_scenario_a_trigger_commit(db: VarysDatabase):
    """Verify get_commits_between retrieves the trigger commit db7a19f for Scenario A."""
    commits = db.get_commits_between("payment-pipeline", start_build=215, end_build=217)
    assert len(commits) == 3

    trigger_commit = next((c for c in commits if c["commit_hash"] == "db7a19f"), None)
    assert trigger_commit is not None
    assert trigger_commit["author"] == "alex.dev@corp.com"
    assert "src/main/resources/application-db.yml" in trigger_commit["files_changed"]
    assert trigger_commit["build_number"] == 216


def test_scenario_b_duration_regression(db: VarysDatabase):
    """Verify Scenario B duration jump starting at build 110."""
    builds = db.get_recent_builds("order-service-build", count=50)
    assert len(builds) == 25

    # All builds in scenario B are SUCCESS
    assert all(b["result"] == "SUCCESS" for b in builds)

    build_map = {b["build_number"]: b["duration_sec"] for b in builds}

    # Baseline builds 101-109
    for b in range(101, 110):
        assert 240.0 <= build_map[b] <= 265.0

    # Build 110 spike
    assert build_map[110] >= 750.0

    # Subsequent builds >= 950s
    for b in range(111, 126):
        assert build_map[b] >= 950.0


def test_scenario_b_trigger_commit(db: VarysDatabase):
    """Verify get_commits_between retrieves trigger commit a1f89c0 with Jenkinsfile for Scenario B."""
    commits = db.get_commits_between("order-service-build", start_build=108, end_build=112)
    assert len(commits) == 5

    trigger_commit = next((c for c in commits if c["commit_hash"] == "a1f89c0"), None)
    assert trigger_commit is not None
    assert trigger_commit["author"] == "ci-ops@corp.com"
    assert "Jenkinsfile" in trigger_commit["files_changed"]
    assert "build.gradle.kts" in trigger_commit["files_changed"]
    assert trigger_commit["build_number"] == 110


def test_scenario_b_test_results_all_passed(db: VarysDatabase):
    """Verify tests in Scenario B are fast and all pass (showing pipeline is the bottleneck)."""
    tests = db.get_test_results("order-service-build", build_number=120)
    assert len(tests) == 2
    assert all(t["status"] == "PASSED" for t in tests)
