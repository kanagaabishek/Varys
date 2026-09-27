"""MCP Server definition exposing Varys CI diagnostics tools."""

from __future__ import annotations

from typing import Any, List, Optional

try:
    from mcp.server.mcpserver import MCPServer
    mcp = MCPServer("varys-jenkins-diagnostics")
except (ImportError, ModuleNotFoundError):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("varys-jenkins-diagnostics")

from varys.mcp.tools import (
    get_commits_between as _get_commits_between,
    get_recent_builds as _get_recent_builds,
    get_test_history as _get_test_history,
    get_test_results as _get_test_results,
)


@mcp.tool()
def get_recent_builds(job_name: str, count: int = 15) -> List[dict[str, Any]]:
    """Retrieves summary metadata (build number, result status, duration in seconds, timestamp, commit hash)

    of the most recent N builds for a given Jenkins job.
    """
    return _get_recent_builds(job_name=job_name, count=count)


@mcp.tool()
def get_test_results(job_name: str, build_number: int) -> List[dict[str, Any]]:
    """Returns execution details and error traces for all test cases run in a specific build."""
    return _get_test_results(job_name=job_name, build_number=build_number)


@mcp.tool()
def get_test_history(job_name: str, test_name: str, count: int = 15) -> List[dict[str, Any]]:
    """Traces the pass/fail/skipped timeline of a single test across previous builds to diagnose flakiness or permanent breakage."""
    return _get_test_history(job_name=job_name, test_name=test_name, count=count)


@mcp.tool()
def get_commits_between(
    job_name: str,
    start_build: Optional[int] = None,
    end_build: Optional[int] = None,
    old_build_number: Optional[int] = None,
    new_build_number: Optional[int] = None,
    build_a: Optional[int] = None,
    build_b: Optional[int] = None,
) -> List[dict[str, Any]]:
    """Fetches git commit metadata and changed file lists between two build numbers."""
    return _get_commits_between(
        job_name=job_name,
        start_build=start_build,
        end_build=end_build,
        old_build_number=old_build_number,
        new_build_number=new_build_number,
        build_a=build_a,
        build_b=build_b,
    )


def main() -> None:
    """Runs the MCP server over stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()
