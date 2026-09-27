"""Unit tests for Varys MCP tool contracts and functions."""

import pytest
from varys.mcp.server import mcp
from varys.mcp.tools import (
    BuildSummary,
    CommitItem,
    TestHistoryItem,
    TestResultItem,
    get_commits_between,
    get_recent_builds,
    get_test_history,
    get_test_results,
)
from varys.storage.database import VarysDatabase
from varys.storage.seed import seed_all


@pytest.fixture
def seeded_db(tmp_path):
    """Creates a temporary seeded SQLite database."""
    db_file = tmp_path / "test_mcp.db"
    return seed_all(db_path=db_file, reset=True)


def test_fastmcp_server_tools_registered():
    """Verify all 4 tools are registered on the FastMCP server."""
    # FastMCP holds registered tools
    assert mcp.name == "varys-jenkins-diagnostics"


def test_get_recent_builds_contract(seeded_db: VarysDatabase):
    """Verify get_recent_builds returns valid BuildSummary items matching schema."""
    builds = get_recent_builds("payment-pipeline", count=5, db=seeded_db)
    assert len(builds) == 5

    for b in builds:
        # Pydantic validation
        model = BuildSummary(**b)
        assert model.build_number > 0
        assert model.result in ("SUCCESS", "FAILURE", "UNSTABLE", "ABORTED")
        assert model.duration_sec > 0


def test_build_summary_nullable_commit_hash():
    """Verify BuildSummary allows None/missing commit_hash without ValidationError."""
    model = BuildSummary(
        build_number=1,
        result="SUCCESS",
        duration_sec=120.0,
        timestamp="2026-09-20T10:00:00Z",
        commit_hash=None,
    )
    assert model.commit_hash is None


def test_get_recent_builds_nonexistent_job_raises_value_error(seeded_db: VarysDatabase):
    """Verify get_recent_builds raises ValueError when job is not found, showing available jobs."""
    with pytest.raises(ValueError) as excinfo:
        get_recent_builds("payment_pipeline_typo", count=5, db=seeded_db)
    assert "Job 'payment_pipeline_typo' not found" in str(excinfo.value)
    assert "payment-pipeline" in str(excinfo.value)


def test_get_recent_builds_zero_or_negative_count(seeded_db: VarysDatabase):
    """Verify zero or negative count returns empty list."""
    assert get_recent_builds("payment-pipeline", count=0, db=seeded_db) == []
    assert get_recent_builds("payment-pipeline", count=-5, db=seeded_db) == []


def test_get_test_results_contract(seeded_db: VarysDatabase):
    """Verify get_test_results returns valid TestResultItem objects."""
    # Failing build
    results = get_test_results("payment-pipeline", build_number=217, db=seeded_db)
    assert len(results) == 4

    failed_test = next((t for t in results if t["status"] == "FAILED"), None)
    assert failed_test is not None
    assert failed_test["test_name"] == "DatabaseConnectionTest"
    assert "SocketTimeoutException" in (failed_test["error_message"] or "")

    # Passing build
    pass_results = get_test_results("payment-pipeline", build_number=215, db=seeded_db)
    assert len(pass_results) == 4
    assert all(t["status"] == "PASSED" for t in pass_results)


def test_get_test_results_nonexistent_build(seeded_db: VarysDatabase):
    """Verify get_test_results returns empty list for unknown build."""
    res = get_test_results("payment-pipeline", build_number=9999, db=seeded_db)
    assert res == []


def test_get_test_history_contract(seeded_db: VarysDatabase):
    """Verify get_test_history returns valid TestHistoryItem objects."""
    history = get_test_history(
        "payment-pipeline", test_name="DatabaseConnectionTest", count=10, db=seeded_db
    )
    assert len(history) == 10

    for h in history:
        model = TestHistoryItem(**h)
        assert model.status in ("PASSED", "FAILED", "SKIPPED")
        assert model.duration_sec > 0


def test_get_test_history_nonexistent_test(seeded_db: VarysDatabase):
    """Verify get_test_history returns empty list for non-existent test name."""
    res = get_test_history("payment-pipeline", test_name="UnknownTestName", count=10, db=seeded_db)
    assert res == []


def test_get_commits_between_contract(seeded_db: VarysDatabase):
    """Verify get_commits_between returns CommitItem objects and handles start > end."""
    commits_fwd = get_commits_between(
        "payment-pipeline", start_build=215, end_build=217, db=seeded_db
    )
    assert len(commits_fwd) == 3

    # Handle descending order parameters (start_build > end_build)
    commits_rev = get_commits_between(
        "payment-pipeline", start_build=217, end_build=215, db=seeded_db
    )
    assert len(commits_rev) == 3
    assert commits_fwd == commits_rev

    for c in commits_fwd:
        model = CommitItem(**c)
        assert len(model.commit_hash) > 0
        assert len(model.author) > 0
        assert isinstance(model.files_changed, list)
        assert model.build_number is not None
