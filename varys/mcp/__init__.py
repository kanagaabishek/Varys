"""MCP (Model Context Protocol) tool contracts and server implementation for Varys."""

from varys.mcp.client import DiscoveredTool, VarysMCPClient
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
    "VarysMCPClient",
    "DiscoveredTool",
    "BuildSummary",
    "TestResultItem",
    "TestHistoryItem",
    "CommitItem",
    "get_recent_builds",
    "get_test_results",
    "get_test_history",
    "get_commits_between",
]
