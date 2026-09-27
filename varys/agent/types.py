"""Data types and models for Varys Agent loop and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentStep:
    """Represents a single step in the agent's multi-turn investigation."""
    step_number: int
    thought: Optional[str] = None
    tool_name: Optional[str] = None
    tool_args: Optional[Dict[str, Any]] = None
    tool_result: Optional[Any] = None
    is_final: bool = False


@dataclass
class Diagnosis:
    """Structured diagnosis delivered by Varys upon completing investigation."""
    job_name: str
    summary: str
    root_cause: str
    evidence_trail: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    raw_response: str = ""
    turns_used: int = 0
    steps: List[AgentStep] = field(default_factory=list)
