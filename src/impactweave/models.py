from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractKind(str, Enum):
    HTTP_JSON = "http-json"
    EVENT_JSON = "event-json"


class FieldType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"


class ContractField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=256)
    type: FieldType
    required: bool = False
    enum: list[Any] | None = None
    minimum: float | None = None
    maximum: float | None = None

    @field_validator("path")
    @classmethod
    def valid_path(cls, value: str) -> str:
        if not value.startswith("/") or ".." in value.split("/"):
            raise ValueError("field paths must be absolute JSON-pointer-like paths")
        return value


class ContractSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    version: str = Field(min_length=1, max_length=64)
    kind: ContractKind
    fields: list[ContractField] = Field(default_factory=list, max_length=2048)

    @field_validator("fields")
    @classmethod
    def unique_paths(cls, value: list[ContractField]) -> list[ContractField]:
        paths = [item.path for item in value]
        if len(paths) != len(set(paths)):
            raise ValueError("contract field paths must be unique")
        return value


class Edge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    producer: str = Field(min_length=1, max_length=128)
    consumer: str = Field(min_length=1, max_length=128)
    contract: str = Field(min_length=1, max_length=128)
    declared: bool = True


class NodeKind(str, Enum):
    COMPONENT = "component"
    CONTRACT = "contract"
    TOOL = "tool"
    POLICY = "policy"
    DATASET = "dataset"
    DEPLOYMENT = "deployment"
    FIXTURE = "fixture"


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.:/@-]+$")
    kind: NodeKind
    label: str | None = Field(default=None, max_length=200)


class EdgeKind(str, Enum):
    PRODUCES = "produces"
    CONSUMES = "consumes"
    CALLS = "calls"
    RETRIEVES = "retrieves"
    GOVERNED_BY = "governed_by"
    DEPLOYS = "deploys"
    DERIVES = "derives"


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=160)
    target: str = Field(min_length=1, max_length=160)
    kind: EdgeKind
    declared: bool = True


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    producer: str = Field(min_length=1, max_length=128)
    consumer: str = Field(min_length=1, max_length=128)
    contract: str = Field(min_length=1, max_length=128)
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(min_length=1, max_length=128)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc)


class ChangeKind(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    COMPATIBLE = "compatible"


class Severity(str, Enum):
    BREAKING = "breaking"
    WARNING = "warning"
    INFO = "info"


class ContractChange(BaseModel):
    contract: str
    path: str
    kind: ChangeKind
    severity: Severity
    reason: str
    before: Any = None
    after: Any = None


class CoverageState(str, Enum):
    OBSERVED = "observed"
    DECLARED = "declared"
    STALE = "stale"
    UNKNOWN = "unknown"


class ImpactFinding(BaseModel):
    consumer: str
    producer: str
    contract: str
    path: str
    severity: Severity
    reason: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_source: str | None = None
    coverage: CoverageState = CoverageState.UNKNOWN
    impact_score: int = Field(default=0, ge=0, le=100)
    graph_path: list[str] = Field(default_factory=list, max_length=32)


class Verdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    REVIEW = "review"


class ImpactReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "2"
    generated_at: datetime
    verdict: Verdict
    changes: list[ContractChange]
    findings: list[ImpactFinding]
    unknown_edges: list[str] = Field(default_factory=list)
    summary: dict[str, int]
    artifact_digest: str = ""

    @field_validator("generated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(timezone.utc)


class TestTarget(BaseModel):
    """A declarative test command and the paths it is known to exercise."""

    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.:/@-]+$")
    command: list[str] = Field(min_length=1, max_length=64)
    paths: list[str] = Field(default_factory=list, max_length=256)
    tags: list[str] = Field(default_factory=list, max_length=32)
    always: bool = False
    estimated_seconds: int = Field(default=0, ge=0, le=86_400)

    @model_validator(mode="after")
    def require_mapping(self) -> TestTarget:
        if not self.always and not self.paths:
            raise ValueError("a non-always test target must declare at least one path glob")
        return self


class TestObservation(BaseModel):
    """Optional, bounded evidence connecting a test to paths it exercised."""

    model_config = ConfigDict(extra="forbid")
    test_id: str = Field(min_length=1, max_length=160)
    paths: list[str] = Field(min_length=1, max_length=512)
    source: str = Field(min_length=1, max_length=128)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def observation_timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc)


class TestPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tracked_paths: list[str] = Field(default_factory=list, max_length=256)
    ignored_paths: list[str] = Field(default_factory=list, max_length=256)
    fallback_on_unknown: bool = True
    max_selected: int = Field(default=512, ge=1, le=100_000)
    stale_after_days: int = Field(default=30, ge=1, le=3650)


class TestDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    test_id: str
    selected: bool
    reason: str
    matched_paths: list[str] = Field(default_factory=list, max_length=512)
    command: list[str] = Field(default_factory=list, max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=32)
    estimated_seconds: int = Field(default=0, ge=0)
    evidence_sources: list[str] = Field(default_factory=list, max_length=32)


class TestPlanVerdict(str, Enum):
    SAFE_SUBSET = "safe_subset"
    FULL_SUITE = "full_suite"
    REVIEW = "review"


class TestPlanReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    verdict: TestPlanVerdict
    changed_paths: list[str] = Field(default_factory=list, max_length=100_000)
    decisions: list[TestDecision] = Field(default_factory=list, max_length=100_000)
    selected_tests: list[str] = Field(default_factory=list, max_length=100_000)
    skipped_tests: list[str] = Field(default_factory=list, max_length=100_000)
    unknown_paths: list[str] = Field(default_factory=list, max_length=100_000)
    fallback_reasons: list[str] = Field(default_factory=list, max_length=128)
    summary: dict[str, int | bool]
    artifact_digest: str = ""
