from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class ImpactFinding(BaseModel):
    consumer: str
    producer: str
    contract: str
    path: str
    severity: Severity
    reason: str
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_source: str | None = None


class Verdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    REVIEW = "review"


class ImpactReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "1"
    generated_at: datetime
    verdict: Verdict
    changes: list[ContractChange]
    findings: list[ImpactFinding]
    unknown_edges: list[str] = Field(default_factory=list)
    summary: dict[str, int]

    @field_validator("generated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(timezone.utc)
