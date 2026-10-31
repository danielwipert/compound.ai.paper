"""Shared Pydantic models (data contracts) used across arms, gates and metrics.

  TS-3.3  DelayFact
  TS-4.1  ExceptionRecord   (every arm's output, one per row)
  TS-5.2  HeaderMap         (Node A output)
  TS-5.4  Fact, FactList    (bus output; sole input to Nodes C and D)
  TS-5.6  Verdict           (Node D output)
"""

import hashlib
import json
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from src.finance import RiskClass
from src.schema import CANONICAL_FIELDS

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

# TS-4.5: the only allowed halt reasons
HaltReason = Literal[
    "PARSE_FAIL",
    "SCHEMA_FAIL",
    "MAP_UNRESOLVED",
    "EXTRACT_FAIL",
    "VERIFY_REJECT",
    "PROVIDER_ERROR",
]

CanonicalField = Literal[tuple(CANONICAL_FIELDS)]

MAX_REPORT_WORDS = 120


class DelayFact(BaseModel):
    """One structured fact extracted from a carrier note (TS-3.3)."""

    model_config = ConfigDict(extra="forbid")

    cause: Cause
    secondary_cause: Optional[Cause] = None
    delay_hours: Optional[int] = None
    delay_days: Optional[int] = None
    location: Optional[str] = None


class ExceptionRecord(BaseModel):
    """Every arm's output for one row (TS-4.1).

    A HALT record only needs order_item_id, status and halt_reason; the other
    fields may be left empty because the arm declined to answer.
    """

    model_config = ConfigDict(extra="forbid")

    order_item_id: int
    header_map: dict[str, str] = {}
    delay_facts: list[DelayFact] = []
    cost_basis: Optional[float] = None
    profit_ratio_recomputed: Optional[float] = None
    delay_days: Optional[int] = None
    risk_class: Optional[RiskClass] = None
    report: str = ""
    citations: list[str] = []
    status: Literal["OK", "HALT"]
    halt_reason: Optional[HaltReason] = None

    @field_validator("report")
    @classmethod
    def report_word_limit(cls, report: str) -> str:
        if len(report.split()) > MAX_REPORT_WORDS:
            raise ValueError(f"report is over {MAX_REPORT_WORDS} words")
        return report

    @model_validator(mode="after")
    def status_matches_fields(self) -> "ExceptionRecord":
        if self.status == "HALT" and self.halt_reason is None:
            raise ValueError("HALT needs a halt_reason")
        if self.status == "OK":
            if self.halt_reason is not None:
                raise ValueError("OK must not have a halt_reason")
            missing = [
                name for name in ("cost_basis", "profit_ratio_recomputed", "delay_days", "risk_class")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"OK record is missing {missing}")
        return self


class HeaderMap(BaseModel):
    """Node A output: noisy header -> canonical field (TS-5.2)."""

    model_config = ConfigDict(extra="forbid")

    mapping: dict[str, CanonicalField]
    unresolved: list[str] = []
    confidence: dict[str, float] = {}


class Fact(BaseModel):
    """One entry in a FactList (TS-5.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str  # "F1", "F2", ...
    field: str
    value: Union[int, float, str]
    source: Literal["BUS", "NODE_B"]


def fact_list_digest(order_item_id: int, facts: list[Fact]) -> str:
    """sha256 of the canonical JSON of the FactList contents (TS-5.4)."""
    payload = {"order_item_id": order_item_id, "facts": [f.model_dump() for f in facts]}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class FactList(BaseModel):
    """Immutable, hashed facts for one row; sole input to Nodes C and D (TS-5.4)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    order_item_id: int
    facts: tuple[Fact, ...]
    digest: str

    @classmethod
    def build(cls, order_item_id: int, facts: list[Fact]) -> "FactList":
        return cls(order_item_id=order_item_id, facts=tuple(facts), digest=fact_list_digest(order_item_id, facts))

    @model_validator(mode="after")
    def digest_matches(self) -> "FactList":
        if self.digest != fact_list_digest(self.order_item_id, list(self.facts)):
            raise ValueError("FactList digest does not match its facts")
        return self

    def keys(self) -> set[str]:
        return {f.key for f in self.facts}


class Verdict(BaseModel):
    """Node D output (TS-5.6)."""

    model_config = ConfigDict(extra="forbid")

    accept: bool
    unsupported_claims: list[str] = []
    missing_citations: list[str] = []
