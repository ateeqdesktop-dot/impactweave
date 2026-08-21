from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import ContractSnapshot, Edge, Evidence

MAX_BYTES = 2_000_000
MAX_JSONL_LINE = 256_000


class ProjectManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contracts: list[ContractSnapshot] = Field(min_length=1, max_length=512)
    proposed: list[ContractSnapshot] = Field(default_factory=list, max_length=512)
    edges: list[Edge] = Field(default_factory=list, max_length=4096)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100_000)
    strict: bool = True

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
