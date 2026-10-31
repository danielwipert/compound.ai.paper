"""Shared Pydantic models (data contracts) used across arms, gates and metrics.

TS-3.3 DelayFact. More models (ExceptionRecord, HeaderMap, FactList, ...) are
added here as the arms are built.
"""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

Cause = Literal[
    "PORT_CONGESTION",
    "CUSTOMS",
    "WEATHER",
    "LABOUR",
    "MECHANICAL",
    "ADDRESS_ISSUE",
    "CAPACITY",
    "UNKNOWN",
]


class DelayFact(BaseModel):
    """One structured fact extracted from a carrier note (TS-3.3)."""

    model_config = ConfigDict(extra="forbid")

    cause: Cause
    secondary_cause: Optional[Cause] = None
    delay_hours: Optional[int] = None
    delay_days: Optional[int] = None
    location: Optional[str] = None
