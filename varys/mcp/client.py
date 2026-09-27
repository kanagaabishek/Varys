"""MCP Client wrapper for Varys that connects to server.py over stdio."""

from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@dataclass
class DiscoveredTool:
    """Represents a tool dynamically discovered from the MCP server."""
    name: str
    description: str
    parameters_schema: Dict[str, Any]

    def to_gemini_declaration(self) -> Dict[str, Any]:
        """Converts to Google Gemini / OpenAI compatible function declaration schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
        }

    def to_anthropic_schema(self) -> Dict[str, Any]:
        """Converts to Anthropic Claude tool format."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters_schema,
        }


class VarysMCPClient:
    """Client that communicates with Varys MCP server over stdio transport."""

    def __init__(self, server_module: str = "varys.mcp.server") -> None:
        self.server_module = server_module
        self.server_params = StdioServerParameters(
            command=sys.executable,
            args=["-m", self.server_module],
        )

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[VarysMCPClientSession]:
        """Spawns server subprocess and establishes stdio ClientSession."""
        async with stdio_client(self.server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield VarysMCPClientSession(session)


class VarysMCPClientSession:
    """Active session wrapper for executing dynamic tool queries and calls."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session

    async def list_tools(self) -> List[DiscoveredTool]:
        """Dynamically queries available tools and schemas from the MCP server."""
        result = await self._session.list_tools()
        tools = []
        for t in result.tools:
            schema = getattr(t, "input_schema", getattr(t, "inputSchema", {})) or {}
            tools.append(
                DiscoveredTool(
                    name=t.name,
                    description=t.description or "",
                    parameters_schema=schema,
                )
            )
        return tools

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a tool call over stdio and returns the parsed result."""
        response = await self._session.call_tool(name, arguments)
        is_err = getattr(response, "is_error", getattr(response, "isError", False))
        if is_err:
            error_text = ""
            if response.content:
                error_text = response.content[0].text if hasattr(response.content[0], "text") else str(response.content[0])
            raise RuntimeError(f"MCP Tool Error from '{name}': {error_text}")

        # Parse all content items from MCP response
        if not response.content:
            return []

        parsed_items = []
        for item in response.content:
            if hasattr(item, "text"):
                try:
                    parsed_items.append(json.loads(item.text))
                except Exception:
                    parsed_items.append(item.text)
            else:
                parsed_items.append(item)

        # If a single item is a collection or scalar, unwrap if appropriate
        if len(parsed_items) == 1 and isinstance(parsed_items[0], list):
            return parsed_items[0]
        return parsed_items
