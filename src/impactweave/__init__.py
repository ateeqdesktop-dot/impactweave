"""Deterministic change-impact rehearsal for distributed-system contracts."""

from .engine import build_report
from .loader import ProjectManifest, load_manifest
from .models import ImpactReport

__all__ = ["ImpactReport", "ProjectManifest", "build_report", "load_manifest"]
__version__ = "0.2.0"
