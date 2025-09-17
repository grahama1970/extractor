from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, StrictBool, StrictFloat, StrictInt, StrictStr


class IterMetrics(BaseModel):
    approach: StrictStr
    correctness: Dict[StrictStr, StrictBool]
    timings_ms: Dict[StrictStr, float]
    robust: StrictBool
    loc: StrictInt


class MutationInfo(BaseModel):
    applied: StrictBool
    # freeform extras allowed
    model_config = dict(extra="allow")


class IterSummary(BaseModel):
    iter: StrictInt
    score: StrictFloat
    metrics: IterMetrics
    stderr_lines: StrictInt
    stdout_lines: StrictInt
    mutation: Optional[MutationInfo] = None


class DoneInfo(BaseModel):
    ok: StrictBool
    variant: StrictStr
    best_score: Optional[StrictFloat] = None
    best_iter: Optional[StrictInt] = None


class ApproachScore(BaseModel):
    correctness: Dict[StrictStr, StrictBool]
    timings_ms: Dict[StrictStr, float]
    robust: StrictBool
    loc: StrictInt
    speed_points: Dict[StrictStr, StrictFloat]
    brevity_points: StrictFloat
    total_points: StrictFloat


class Scorecard(BaseModel):
    scales: List[StrictStr]
    approaches: Dict[StrictStr, ApproachScore]
    winner: Optional[StrictStr] = None

    def validate_winner(self) -> None:
        if self.winner and self.winner not in self.approaches:
            raise ValueError("winner must be a key in approaches when set")
