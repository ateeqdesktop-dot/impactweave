from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from .models import ContractSnapshot, Edge, Evidence, GraphEdge, GraphNode, TestObservation, TestPolicy, TestTarget

MAX_BYTES = 2_000_000
MAX_JSONL_LINE = 256_000


class ProjectManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contracts: list[ContractSnapshot] = Field(min_length=1, max_length=512)
    proposed: list[ContractSnapshot] = Field(default_factory=list, max_length=512)
    edges: list[Edge] = Field(default_factory=list, max_length=4096)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100_000)
    nodes: list[GraphNode] = Field(default_factory=list, max_length=8192)
    graph_edges: list[GraphEdge] = Field(default_factory=list, max_length=16384)
    strict: bool = True
    max_hops: int = Field(default=8, ge=1, le=32)
    stale_after_days: int = Field(default=30, ge=1, le=3650)
    tests: list[TestTarget] = Field(default_factory=list, max_length=100_000)
    test_observations: list[TestObservation] = Field(default_factory=list, max_length=100_000)
    test_policy: TestPolicy = Field(default_factory=TestPolicy)

    @model_validator(mode="after")
    def validate_graph_references(self) -> ProjectManifest:
        node_ids = {node.id for node in self.nodes}
        missing = sorted(
            {item for edge in self.graph_edges for item in (edge.source, edge.target) if item not in node_ids}
        )
        if missing:
            raise ValueError(f"graph edges reference unknown nodes: {', '.join(missing)}")
        test_ids = [item.id for item in self.tests]
        if len(test_ids) != len(set(test_ids)):
            raise ValueError("test target ids must be unique")
        unknown_tests = sorted({item.test_id for item in self.test_observations if item.test_id not in set(test_ids)})
        if unknown_tests:
            raise ValueError(f"test observations reference unknown tests: {', '.join(unknown_tests)}")
        return self

    @property
    def contract_map(self) -> dict[str, ContractSnapshot]:
        return {item.name: item for item in self.contracts}

    @property
    def proposed_map(self) -> dict[str, ContractSnapshot]:
        return {item.name: item for item in self.proposed}


def _read(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"input exceeds {MAX_BYTES} bytes: {path}")
    return path.read_text(encoding="utf-8")


def load_manifest(path: str | Path) -> ProjectManifest:
    raw = yaml.safe_load(_read(Path(path)))
    if not isinstance(raw, dict):
        raise ValueError("manifest root must be an object")
    try:
        return ProjectManifest.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid manifest: {exc}") from exc


def load_json(path: str | Path) -> Any:
    try:
        return json.loads(_read(Path(path)))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc


def load_evidence_jsonl(path: str | Path) -> list[Evidence]:
    result: list[Evidence] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            if len(raw_line.encode("utf-8")) > MAX_JSONL_LINE:
                raise ValueError(f"JSONL line {line_number} exceeds {MAX_JSONL_LINE} bytes")
            line = raw_line.strip()
            if not line:
                continue
            try:
                result.append(Evidence.model_validate(json.loads(line)))
            except (json.JSONDecodeError, ValidationError) as exc:
                raise ValueError(f"invalid evidence at line {line_number}: {exc}") from exc
    return result
