"""Typed MCP Tool implementations and Pydantic contracts for Varys."""

from __future__ import annotations

from typing import Any, List, Optional
from pydantic import BaseModel, Field

from varys.storage.database import VarysDatabase, get_db


# --- Pydantic Data Contracts ---

class BuildSummary(BaseModel):
    build_number: int = Field(..., description="The unique sequential build number")
    result: str = Field(..., description="Build outcome: SUCCESS, FAILURE, UNSTABLE, or ABORTED")
    duration_sec: float = Field(..., description="Total pipeline execution duration in seconds")
    timestamp: str = Field(..., description="ISO 8601 timestamp of build start")
    commit_hash: Optional[str] = Field(None, description="Git commit hash associated with this build")


class TestResultItem(BaseModel):
    __test__ = False
    test_name: str = Field(..., description="Name of the test class or test method")
    suite_name: str = Field(..., description="Test suite or package name")
    status: str = Field(..., description="Outcome: PASSED, FAILED, or SKIPPED")
    duration_sec: float = Field(..., description="Test execution duration in seconds")
    error_message: Optional[str] = Field(None, description="Failure summary or assertion message")
    stack_trace: Optional[str] = Field(None, description="Detailed error stack trace if failed")


class TestHistoryItem(BaseModel):
    __test__ = False
    build_number: int = Field(..., description="Build number where test ran")
    status: str = Field(..., description="Outcome in this build: PASSED, FAILED, or SKIPPED")
    duration_sec: float = Field(..., description="Duration in seconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class CommitItem(BaseModel):
    commit_hash: str = Field(..., description="Git commit SHA")
    job_name: str = Field(..., description="Job or pipeline name")
    author: str = Field(..., description="Author name or email")
    message: str = Field(..., description="Git commit message")
    files_changed: List[str] = Field(default_factory=list, description="List of file paths modified")
    diff_summary: Optional[str] = Field(None, description="Brief diff stat (e.g. insertions/deletions)")
    timestamp: str = Field(..., description="ISO 8601 commit timestamp")
    build_number: Optional[int] = Field(None, description="Corresponding build number in Jenkins")


# --- Core Tool Functions ---

def get_recent_builds(
    job_name: str,
    count: int = 15,
    db: Optional[VarysDatabase] = None,
    db_path: str = "varys.db",
) -> List[dict[str, Any]]:
    """Retrieves summary metadata of the most recent N builds for a given Jenkins job."""
    if count <= 0:
        return []
    database = db or get_db(db_path)
    raw = database.get_recent_builds(job_name=job_name, count=count)
    return [BuildSummary(**r).model_dump() for r in raw]


def get_test_results(
    job_name: str,
    build_number: int,
    db: Optional[VarysDatabase] = None,
    db_path: str = "varys.db",
) -> List[dict[str, Any]]:
    """Returns execution details and error traces for all test cases run in a specific build."""
    database = db or get_db(db_path)
    raw = database.get_test_results(job_name=job_name, build_number=build_number)
    return [TestResultItem(**r).model_dump() for r in raw]


def get_test_history(
    job_name: str,
    test_name: str,
    count: int = 15,
    db: Optional[VarysDatabase] = None,
    db_path: str = "varys.db",
) -> List[dict[str, Any]]:
    """Traces the pass/fail timeline of a single test across previous builds to diagnose flakiness."""
    if count <= 0:
        return []
    database = db or get_db(db_path)
    raw = database.get_test_history(job_name=job_name, test_name=test_name, count=count)
    return [TestHistoryItem(**r).model_dump() for r in raw]


def get_commits_between(
    job_name: str,
    start_build: Optional[int] = None,
    end_build: Optional[int] = None,
    old_build_number: Optional[int] = None,
    new_build_number: Optional[int] = None,
    from_build_number: Optional[int] = None,
    to_build_number: Optional[int] = None,
    from_build: Optional[int] = None,
    to_build: Optional[int] = None,
    build_number_1: Optional[int] = None,
    build_number_2: Optional[int] = None,
    build_a: Optional[int] = None,
    build_b: Optional[int] = None,
    db: Optional[VarysDatabase] = None,
    db_path: str = "varys.db",
    **kwargs: Any,
) -> List[dict[str, Any]]:
    """Fetches git commit metadata and changed file lists between two build numbers."""
    candidates_start = [start_build, old_build_number, from_build_number, from_build, build_number_1, build_a, kwargs.get("start"), kwargs.get("from")]
    candidates_end = [end_build, new_build_number, to_build_number, to_build, build_number_2, build_b, kwargs.get("end"), kwargs.get("to")]

    sb = next((x for x in candidates_start if x is not None), None)
    eb = next((x for x in candidates_end if x is not None), None)

    if sb is None or eb is None:
        raise ValueError("Both start_build and end_build (or aliases) are required.")

    database = db or get_db(db_path)
    raw = database.get_commits_between(
        job_name=job_name, start_build=int(sb), end_build=int(eb)
    )
    return [CommitItem(**r).model_dump() for r in raw]
