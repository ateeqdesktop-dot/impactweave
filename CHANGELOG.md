# Changelog

All notable changes to ImpactWeave Nexus are documented here.

## [0.2.0] — 2026-08-24

### Added

- Typed graph nodes and edges for components, contracts, tools, policies, datasets, deployments, and fixtures.
- Bounded deterministic graph-path resolution for explainable producer-to-consumer findings.
- Evidence coverage states: observed, stale, and unknown.
- Bounded impact scores and stable SHA-256 artifact digests.
- SARIF 2.1.0 output for GitHub Code Scanning-compatible workflows.
- `nexus` CLI command while preserving the existing `plan` command.
- Nexus fixture, architecture documentation, and focused regression tests.

### Changed

- Reports now use schema version 2 and include graph paths, coverage, scores, and fresh-evidence semantics.
- Package metadata and public version updated to 0.2.0.
- CI now validates the Nexus fixture and SARIF artifact in addition to Ruff, mypy, pytest, and build checks.

### Compatibility

Existing manifests using `contracts`, `proposed`, `edges`, `evidence`, and `strict` continue to work. New graph fields are optional.
