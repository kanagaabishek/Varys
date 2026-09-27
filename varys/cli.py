"""Command-line interface for Varys CI Intelligence Agent."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from varys.agent.loop import VarysAgent
from varys.agent.types import AgentStep, Diagnosis
from varys.storage.seed import seed_all

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(highlight=False)


def render_step(step: AgentStep) -> None:
    """Renders a single reasoning step live to terminal."""
    tool_args_str = ", ".join(f"{k}={v!r}" for k, v in (step.tool_args or {}).items())
    console.print(f"  ├── ⚙️ [bold blue]Step {step.step_number}:[/] [italic]{step.thought}[/]")
    console.print(f"  │   └── 📞 [cyan]MCP Call:[/] [bold]{step.tool_name}[/]({tool_args_str})")

    # Format result snippet
    if step.tool_result is not None:
        if isinstance(step.tool_result, list):
            res_summary = f"{len(step.tool_result)} items returned"
            if len(step.tool_result) > 0 and isinstance(step.tool_result[0], dict):
                first_keys = list(step.tool_result[0].keys())[:3]
                res_summary += f" (sample keys: {first_keys})"
        elif isinstance(step.tool_result, dict):
            res_summary = f"{list(step.tool_result.keys())}"
        else:
            res_summary = str(step.tool_result)[:80]
        console.print(f"  │   └── 📊 [green]Result:[/] {res_summary}")
    console.print("  │")


def render_diagnosis(diagnosis: Diagnosis) -> None:
    """Renders the final structured diagnosis in a rich panel."""
    console.print("  └── ✨ [bold green]Investigation Complete![/]\n")

    md = Markdown(diagnosis.raw_response)
    panel = Panel(
        md,
        title="[bold yellow]🕵️ VARYS PIPELINE DIAGNOSIS REPORT[/]",
        subtitle=f"[dim]Turns used: {diagnosis.turns_used} | Target: {diagnosis.job_name}[/]",
        box=box.ROUNDED,
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)


async def async_main(args: argparse.Namespace) -> None:
    # Ensure database exists
    db_file = Path(args.db_path)
    if not db_file.exists():
        console.print(f"[dim]Initializing and seeding database {args.db_path}...[/dim]")
        seed_all(db_path=args.db_path, reset=True)

    console.print("\n[bold cyan]🔎 VARYS CI Intelligence Agent[/] — Initializing investigation...")
    console.print(f"[dim]Question:[/] [yellow]\"{args.query}\"[/]\n")

    agent = VarysAgent(
        model_name=args.model,
        api_key=args.api_key,
        max_turns=args.max_turns,
        db_path=args.db_path,
    )

    is_mock = args.mock or not (args.api_key or os.environ.get("GEMINI_API_KEY"))
    if is_mock and not args.mock:
        console.print("[dim yellow]No GEMINI_API_KEY detected. Running in deterministic mock runner mode.[/dim yellow]\n")

    diagnosis = await agent.run(
        query=args.query,
        on_step=render_step,
        mock=args.mock,
    )

    render_diagnosis(diagnosis)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Varys - Autonomous Jenkins CI Intelligence & Diagnostics Agent"
    )
    parser.add_argument("query", help="Investigation question (e.g. 'why is payment-pipeline unstable?')")
    parser.add_argument("--model", default="gemini-2.5-flash", help="LLM model (default: gemini-2.5-flash)")
    parser.add_argument("--api-key", default=None, help="Gemini API Key (or set GEMINI_API_KEY env)")
    parser.add_argument("--mock", action="store_true", help="Run in deterministic offline mode")
    parser.add_argument("--max-turns", type=int, default=5, help="Max tool-use turns (default: 5)")
    parser.add_argument("--db-path", default="varys.db", help="Path to SQLite database")

    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == "__main__":
    main()
