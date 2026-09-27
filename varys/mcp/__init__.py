"""MCP (Model Context Protocol) tool contracts and server implementation for Varys."""

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

__all__ = [
    "BuildSummary",
    "TestResultItem",
    "TestHistoryItem",
    "CommitItem",
    "get_recent_builds",
    "get_test_results",
    "get_test_history",
    "get_commits_between",
]
