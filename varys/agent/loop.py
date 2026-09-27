"""Autonomous multi-turn ReAct Agent loop using MCP over stdio."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Callable, Dict, List, Optional

from google import genai
from google.genai import types

from varys.agent.prompts import SYSTEM_PROMPT
from varys.agent.types import AgentStep, Diagnosis
from varys.mcp.client import DiscoveredTool, VarysMCPClient


class VarysAgent:
    """Autonomous agent that plans and executes CI investigations through MCP tools."""

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        max_turns: int = 5,
        db_path: str = "varys.db",
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.max_turns = max_turns
        self.db_path = db_path
        self.mcp_client = VarysMCPClient()

    async def run(
        self,
        query: str,
        on_step: Optional[Callable[[AgentStep], None]] = None,
        mock: bool = False,
    ) -> Diagnosis:
        """Executes the investigation loop and returns structured diagnosis."""
        if mock or not self.api_key:
            return await self._run_deterministic_mock(query, on_step)

        return await self._run_gemini_loop(query, on_step)

    async def _run_gemini_loop(
        self,
        query: str,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> Diagnosis:
        """Runs the live multi-turn ReAct loop against Gemini with dynamic stdio MCP tools."""
        ai_client = genai.Client(api_key=self.api_key)

        steps: List[AgentStep] = []
        conversation_history: List[types.Content] = []

        async with self.mcp_client.connect() as session:
            # 1. Discover tools dynamically over stdio
            discovered_tools: List[DiscoveredTool] = await session.list_tools()
            func_decls = [t.to_gemini_declaration() for t in discovered_tools]

            config = types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[{"function_declarations": func_decls}],
                temperature=0.1,
            )

            # Initial user prompt
            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=query)],
            )
            conversation_history.append(user_content)

            final_text = ""
            for turn in range(1, self.max_turns + 1):
                # Call Gemini with conversation history
                response = ai_client.models.generate_content(
                    model=self.model_name,
                    contents=conversation_history,
                    config=config,
                )

                candidate = response.candidates[0]
                model_content = candidate.content
                conversation_history.append(model_content)

                # Check if model requested function calls
                function_calls = []
                for part in model_content.parts:
                    if part.function_call:
                        function_calls.append(part.function_call)

                if not function_calls:
                    # Model produced final diagnosis text (no more tool calls)
                    final_text = response.text or ""
                    break

                # Execute requested function calls via MCP over stdio
                function_response_parts = []
                for fc in function_calls:
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}

                    step = AgentStep(
                        step_number=turn,
                        thought=f"Executing {tool_name} to gather evidence",
                        tool_name=tool_name,
                        tool_args=tool_args,
                    )

                    try:
                        tool_output = await session.call_tool(tool_name, tool_args)
                        step.tool_result = tool_output
                    except Exception as e:
                        tool_output = {"error": str(e)}
                        step.tool_result = tool_output

                    steps.append(step)
                    if on_step:
                        on_step(step)

                    # Build tool response part
                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": tool_output},
                        )
                    )

                # Feed function responses back into conversation history
                conversation_history.append(
                    types.Content(
                        role="user",
                        parts=function_response_parts,
                    )
                )

            # If max turns reached without text, ask model to synthesize
            if not final_text:
                synth_response = ai_client.models.generate_content(
                    model=self.model_name,
                    contents=conversation_history
                    + [
                        types.Content(
                            role="user",
                            parts=[
                                types.Part.from_text(
                                    text="Iteration cap reached. Synthesize all collected evidence into your final diagnosis now."
                                )
                            ],
                        )
                    ],
                )
                final_text = synth_response.text or "Diagnosis completed based on collected evidence."

            return Diagnosis(
                job_name=self._extract_job_name(query, steps),
                summary="Pipeline Investigation Completed",
                root_cause="",
                evidence_trail=[f"Analyzed {len(steps)} diagnostic steps via MCP"],
                raw_response=final_text,
                turns_used=len(steps),
                steps=steps,
            )

    async def _run_deterministic_mock(
        self,
        query: str,
        on_step: Optional[Callable[[AgentStep], None]] = None,
    ) -> Diagnosis:
        """Deterministic ReAct runner for offline demos and zero-dependency testing."""
        steps: List[AgentStep] = []
        job_name = "payment-pipeline" if "payment" in query.lower() else "order-service-build"

        async with self.mcp_client.connect() as session:
            # Step 1: get_recent_builds
            step1 = AgentStep(
                step_number=1,
                thought="Checking recent build history to quantify pipeline health",
                tool_name="get_recent_builds",
                tool_args={"job_name": job_name, "count": 20},
            )
            step1.tool_result = await session.call_tool("get_recent_builds", step1.tool_args)
            steps.append(step1)
            if on_step:
                on_step(step1)

            if job_name == "payment-pipeline":
                # Step 2: get_test_results for failing build #230
                step2 = AgentStep(
                    step_number=2,
                    thought="Inspecting failing tests in latest build #230",
                    tool_name="get_test_results",
                    tool_args={"job_name": job_name, "build_number": 230},
                )
                step2.tool_result = await session.call_tool("get_test_results", step2.tool_args)
                steps.append(step2)
                if on_step:
                    on_step(step2)

                # Step 3: get_test_history for DatabaseConnectionTest
                step3 = AgentStep(
                    step_number=3,
                    thought="Evaluating historical pattern of DatabaseConnectionTest to check for flakiness",
                    tool_name="get_test_history",
                    tool_args={"job_name": job_name, "test_name": "DatabaseConnectionTest", "count": 15},
                )
                step3.tool_result = await session.call_tool("get_test_history", step3.tool_args)
                steps.append(step3)
                if on_step:
                    on_step(step3)

                # Step 4: get_commits_between
                step4 = AgentStep(
                    step_number=4,
                    thought="Correlating failure onset between baseline build #215 and #217 with git commits",
                    tool_name="get_commits_between",
                    tool_args={"job_name": job_name, "start_build": 215, "end_build": 217},
                )
                step4.tool_result = await session.call_tool("get_commits_between", step4.tool_args)
                steps.append(step4)
                if on_step:
                    on_step(step4)

                raw_resp = (
                    "### SUMMARY\n"
                    "`payment-pipeline` has experienced 6 failures in the last 15 builds (40% failure rate) "
                    "starting at build #217.\n\n"
                    "### ROOT CAUSE\n"
                    "Commit `db7a19f` ('chore(db): update hikari connection pool timeout and idle limits') "
                    "by alex.dev@corp.com reduced connection acquisition timeouts from 10s to 5s, triggering "
                    "intermittent `SocketTimeoutException` in `DatabaseConnectionTest`.\n\n"
                    "### KEY EVIDENCE\n"
                    "- `DatabaseConnectionTest` exhibits an alternating pass/fail flaky pattern across builds #217–#230.\n"
                    "- Baseline builds #201–#215 had 100% pass rate.\n"
                    "- Commit `db7a19f` landed immediately before the first failure (#217) modifying `application-db.yml`.\n\n"
                    "### RECOMMENDATIONS\n"
                    "1. Revert connection timeout reduction in `src/main/resources/application-db.yml` or increase pool capacity.\n"
                    "2. Add testcontainer warmup hooks to stabilize CI database initialization."
                )
            else:
                # Scenario B: duration regression
                step2 = AgentStep(
                    step_number=2,
                    thought="Correlating duration regression onset around build #110 with code commits",
                    tool_name="get_commits_between",
                    tool_args={"job_name": job_name, "start_build": 108, "end_build": 112},
                )
                step2.tool_result = await session.call_tool("get_commits_between", step2.tool_args)
                steps.append(step2)
                if on_step:
                    on_step(step2)

                raw_resp = (
                    "### SUMMARY\n"
                    "`order-service-build` durations ballooned from ~4 minutes (250s) to over 16 minutes (>950s) "
                    "starting at build #110, while all test suites continue to pass in ~45s.\n\n"
                    "### ROOT CAUSE\n"
                    "Commit `a1f89c0` ('build(gradle): add full container image scan step to pipeline') "
                    "introduced a container vulnerability scan step without layer caching.\n\n"
                    "### KEY EVIDENCE\n"
                    "- Build duration spiked from 250s to 780s at #110, and exceeded 950s for subsequent builds.\n"
                    "- Test execution time remained constant at 45s, proving pipeline step bottleneck.\n"
                    "- Commit `a1f89c0` modified `Jenkinsfile` and `build.gradle.kts`.\n\n"
                    "### RECOMMENDATIONS\n"
                    "1. Enable Docker layer caching for container vulnerability scans in Jenkinsfile.\n"
                    "2. Move full container vulnerability scan to nightly or async post-merge pipeline."
                )

            return Diagnosis(
                job_name=job_name,
                summary="Investigation Completed",
                root_cause="",
                evidence_trail=[f"Executed {len(steps)} steps via MCP"],
                raw_response=raw_resp,
                turns_used=len(steps),
                steps=steps,
            )

    def _extract_job_name(self, query: str, steps: List[AgentStep]) -> str:
        for s in steps:
            if s.tool_args and "job_name" in s.tool_args:
                return s.tool_args["job_name"]
        return "jenkins-pipeline"
