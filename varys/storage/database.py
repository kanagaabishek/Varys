"""SQLite database access object and query methods for Varys."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional


@dataclass
class JobRecord:
    name: str
    description: str = ""
    repository_url: str = ""


@dataclass
class CommitRecord:
    commit_hash: str
    job_name: str
    author: str
    message: str
    files_changed: List[str]
    diff_summary: str = ""
    timestamp: str = ""
    build_number: Optional[int] = None


@dataclass
class BuildRecord:
    id: Optional[int]
    job_name: str
    build_number: int
    result: str
    duration_sec: float
    timestamp: str
    commit_hash: Optional[str] = None


@dataclass
class TestResultRecord:
    __test__ = False
    id: Optional[int]
    job_name: str
    build_number: int
    test_name: str
    suite_name: str
    status: str
    duration_sec: float
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None


class VarysDatabase:
    """Manages SQLite database connections, schema setup, and query execution."""

    def __init__(self, db_path: str | Path = "varys.db") -> None:
        self.db_path = str(db_path)
        self.init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_schema(self) -> None:
        """Creates tables and indexes if they do not already exist."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    name TEXT PRIMARY KEY,
                    description TEXT,
                    repository_url TEXT
                );

                CREATE TABLE IF NOT EXISTS commits (
                    commit_hash TEXT PRIMARY KEY,
                    job_name TEXT NOT NULL,
                    author TEXT NOT NULL,
                    message TEXT NOT NULL,
                    files_changed TEXT NOT NULL,
                    diff_summary TEXT,
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS builds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_name TEXT NOT NULL,
                    build_number INTEGER NOT NULL,
                    result TEXT CHECK(result IN ('SUCCESS', 'FAILURE', 'UNSTABLE', 'ABORTED')),
                    duration_sec REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    commit_hash TEXT,
                    FOREIGN KEY(job_name) REFERENCES jobs(name),
                    FOREIGN KEY(commit_hash) REFERENCES commits(commit_hash),
                    UNIQUE(job_name, build_number)
                );

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

                CREATE INDEX IF NOT EXISTS idx_builds_job_num ON builds(job_name, build_number);
                CREATE INDEX IF NOT EXISTS idx_test_results_job_build ON test_results(job_name, build_number);
                CREATE INDEX IF NOT EXISTS idx_test_results_lookup ON test_results(job_name, test_name, build_number);
                """
            )

    def reset_database(self) -> None:
        """Drops all tables and re-initializes clean schema."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                DROP TABLE IF EXISTS test_results;
                DROP TABLE IF EXISTS builds;
                DROP TABLE IF EXISTS commits;
                DROP TABLE IF EXISTS jobs;
                """
            )
        self.init_schema()

    def validate_job_exists(self, job_name: str) -> None:
        """Validates that a job exists in the database. Raises ValueError with available jobs on failure."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT name FROM jobs WHERE name = ?", (job_name,)).fetchone()
            if not row:
                all_jobs = [r["name"] for r in conn.execute("SELECT name FROM jobs ORDER BY name ASC").fetchall()]
                raise ValueError(
                    f"Job '{job_name}' not found. Available jobs in system: {all_jobs}"
                )

    # --- Insertion Methods ---

    def insert_job(self, job: JobRecord) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO jobs (name, description, repository_url)
                VALUES (?, ?, ?)
                """,
                (job.name, job.description, job.repository_url),
            )

    def insert_commit(self, commit: CommitRecord) -> None:
        files_json = (
            json.dumps(commit.files_changed)
            if isinstance(commit.files_changed, list)
            else commit.files_changed
        )
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO commits (commit_hash, job_name, author, message, files_changed, diff_summary, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    commit.commit_hash,
                    commit.job_name,
                    commit.author,
                    commit.message,
                    files_json,
                    commit.diff_summary,
                    commit.timestamp,
                ),
            )

    def insert_build(self, build: BuildRecord) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO builds (job_name, build_number, result, duration_sec, timestamp, commit_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    build.job_name,
                    build.build_number,
                    build.result,
                    build.duration_sec,
                    build.timestamp,
                    build.commit_hash,
                ),
            )
            return cursor.lastrowid or 0

    def insert_test_result(self, test: TestResultRecord) -> int:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO test_results (job_name, build_number, test_name, suite_name, status, duration_sec, error_message, stack_trace)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    test.job_name,
                    test.build_number,
                    test.test_name,
                    test.suite_name,
                    test.status,
                    test.duration_sec,
                    test.error_message,
                    test.stack_trace,
                ),
            )
            return cursor.lastrowid or 0

    # --- Query & Tool Methods ---

    def get_all_jobs(self) -> List[dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM jobs ORDER BY name ASC").fetchall()
            return [dict(r) for r in rows]

    def get_recent_builds(self, job_name: str, count: int = 15) -> List[dict[str, Any]]:
        """Retrieves recent N builds in descending order (latest first)."""
        self.validate_job_exists(job_name)
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT build_number, result, duration_sec, timestamp, commit_hash
                FROM builds
                WHERE job_name = ?
                ORDER BY build_number DESC
                LIMIT ?
                """,
                (job_name, count),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_test_results(self, job_name: str, build_number: int) -> List[dict[str, Any]]:
        """Retrieves test results for a specific build."""
        self.validate_job_exists(job_name)
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT test_name, suite_name, status, duration_sec, error_message, stack_trace
                FROM test_results
                WHERE job_name = ? AND build_number = ?
                ORDER BY test_name ASC
                """,
                (job_name, build_number),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_test_history(self, job_name: str, test_name: str, count: int = 15) -> List[dict[str, Any]]:
        """Retrieves timeline of a single test across recent builds (latest first)."""
        self.validate_job_exists(job_name)
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT build_number, status, duration_sec, error_message
                FROM test_results
                WHERE job_name = ? AND test_name = ?
                ORDER BY build_number DESC
                LIMIT ?
                """,
                (job_name, test_name, count),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_commits_between(
        self, job_name: str, start_build: int, end_build: int
    ) -> List[dict[str, Any]]:
        """Retrieves commits between two build numbers (inclusive) via JOIN."""
        self.validate_job_exists(job_name)
        min_b = min(start_build, end_build)
        max_b = max(start_build, end_build)

        with self._get_connection() as conn:
            rows = conn.execute(
                """
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
                WHERE b.job_name = ? AND b.build_number BETWEEN ? AND ?
                ORDER BY b.build_number ASC
                """,
                (job_name, min_b, max_b),
            ).fetchall()

            results = []
            for r in rows:
                item = dict(r)
                if isinstance(item.get("files_changed"), str):
                    try:
                        item["files_changed"] = json.loads(item["files_changed"])
                    except Exception:
                        pass
                results.append(item)
            return results


_default_db: Optional[VarysDatabase] = None


def get_db(db_path: str | Path = "varys.db") -> VarysDatabase:
    """Returns a singleton instance or new instance for the given path."""
    global _default_db
    if _default_db is None or str(_default_db.db_path) != str(db_path):
        _default_db = VarysDatabase(db_path)
    return _default_db
