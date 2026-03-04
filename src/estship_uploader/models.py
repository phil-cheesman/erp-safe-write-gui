"""Shared data models — StepResult, PipelineResult."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class StepResult:
    """Result of a single pipeline step."""

    status: str  # "PASS", "FAIL", "WARNING"
    message: str
    details: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result of a complete pipeline run."""

    steps: list[StepResult] = field(default_factory=list)
    success: bool = False
