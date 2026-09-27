"""End-to-End tests for Varys MCP Client communicating with Server over stdio."""

import pytest
from varys.mcp.client import VarysMCPClient
from varys.storage.seed import seed_all


@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    """Ensure varys.db is initialized and seeded before running stdio tests."""
    seed_all("varys.db", reset=True)


@pytest.mark.asyncio
async def test_mcp_client_dynamic_tool_discovery():
    """Verify MCP client launches server subprocess and dynamically retrieves all 4 tools."""
    client = VarysMCPClient()
    async with client.connect() as session:
        tools = await session.list_tools()
        tool_names = {t.name for t in tools}

        assert "get_recent_builds" in tool_names
        assert "get_test_results" in tool_names
        assert "get_test_history" in tool_names
        assert "get_commits_between" in tool_names

        # Verify schema export methods for LLMs
        for t in tools:
            gemini_decl = t.to_gemini_declaration()
            assert gemini_decl["name"] == t.name
            assert "parameters" in gemini_decl


@pytest.mark.asyncio
async def test_mcp_client_call_get_recent_builds_over_stdio():
    """Verify MCP client executes get_recent_builds over stdio."""
    client = VarysMCPClient()
    async with client.connect() as session:
        result = await session.call_tool(
            "get_recent_builds",
            {"job_name": "payment-pipeline", "count": 5},
        )
        assert isinstance(result, list)
        assert len(result) == 5
        assert result[0]["build_number"] == 230


@pytest.mark.asyncio
async def test_mcp_client_call_get_commits_between_over_stdio():
    """Verify MCP client executes get_commits_between over stdio."""
    client = VarysMCPClient()
    async with client.connect() as session:
        result = await session.call_tool(
            "get_commits_between",
            {"job_name": "payment-pipeline", "start_build": 215, "end_build": 217},
        )
        assert isinstance(result, list)
        assert len(result) == 3
        trigger = next((c for c in result if c["commit_hash"] == "db7a19f"), None)
        assert trigger is not None
        assert "application-db.yml" in trigger["files_changed"][0]
