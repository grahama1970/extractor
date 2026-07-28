from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, StrictBool, StrictFloat, StrictInt, StrictStr


class IterMetrics(BaseModel):
    """Return metrics for iteration including correctness and timings."""
    approach: StrictStr
    correctness: Dict[StrictStr, StrictBool]
    timings_ms: Dict[StrictStr, float]
    robust: StrictBool
    loc: StrictInt


class MutationInfo(BaseModel):
    """Return mutation application status with flexible extra attributes."""
    applied: StrictBool
    # freeform extras allowed
    model_config = dict(extra="allow")


class IterSummary(BaseModel):
    """Represent a summary of a single iteration's results and metrics."""
    iter: StrictInt
    score: StrictFloat
    metrics: IterMetrics
    stderr_lines: StrictInt
    stdout_lines: StrictInt
    mutation: Optional[MutationInfo] = None


class DoneInfo(BaseModel):
    """Return status and details of a completed operation."""
    ok: StrictBool
    variant: StrictStr
    best_score: Optional[StrictFloat] = None
    best_iter: Optional[StrictInt] = None


class ApproachScore(BaseModel):
    """Represent an approach's evaluation score and metrics."""
    correctness: Dict[StrictStr, StrictBool]
    timings_ms: Dict[StrictStr, float]
    robust: StrictBool
    loc: StrictInt
    speed_points: Dict[StrictStr, StrictFloat]
    brevity_points: StrictFloat
    total_points: StrictFloat


class Scorecard(BaseModel):
    """Validate the winner against the available approaches in the scorecard."""
    scales: List[StrictStr]
    approaches: Dict[StrictStr, ApproachScore]
    winner: Optional[StrictStr] = None

    def validate_winner(self) -> None:
        """Ensure winner is a key in approaches."""
        if self.winner and self.winner not in self.approaches:
            raise ValueError("winner must be a key in approaches when set")
