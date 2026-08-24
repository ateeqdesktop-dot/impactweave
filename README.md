# ImpactWeave Nexus

> **Know what your agent change can break before production teaches you.**

[![CI](https://github.com/ateeqdesktop-dot/impactweave/actions/workflows/ci.yml/badge.svg)](https://github.com/ateeqdesktop-dot/impactweave/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/python-3.10%2B-3776AB)](https://www.python.org/) [![License](https://img.shields.io/badge/license-Apache--2.0-blue)](LICENSE)

ImpactWeave Nexus is a **local-first, deterministic change-impact decision engine for AI-enabled distributed systems**. It turns a contract or repository change into an explainable impact graph, attaches the evidence available for each boundary, and emits a stable artifact that humans and CI can review.

It answers a question that ordinary schema validators, observability dashboards, and runtime policy engines answer only partially:

> **Which agent, tool, data, or service boundary can change because of this diff, what evidence supports that conclusion, and where must a human review uncertainty?**

## Why this project exists

AI-enabled systems are connected by more than imports. A small event or API change can alter a tool contract, a retrieval path, a policy boundary, an agent fixture, or a downstream worker. ImpactWeave Nexus makes those relationships explicit without pretending that an impact score is proof of safety.

The core is intentionally offline and framework-neutral. It does not call an LLM, execute repository code, contact a hosted service, or require a database. Every finding includes a severity, coverage state, confidence when evidence is fresh, and a graph path that a reviewer can inspect.

ImpactWeave Nexus is **not** another observability backend, evaluator, runtime governance engine, sandbox, schema registry, generic dependency graph, or hosted control plane. Observability tells you what happened. Runtime governance controls what may happen. Replay tools protect known failures. Nexus helps decide what deserves attention **before merge**.

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Validate without producing an impact decision
impactweave validate fixtures/nexus.yaml

# Produce a human-readable report; this fixture intentionally returns exit 1
impactweave nexus fixtures/nexus.yaml --format markdown --output impact.md

# Produce stable machine output for snapshots and artifacts
impactweave nexus fixtures/nexus.yaml --format json --output impact.json

# Produce SARIF for GitHub Code Scanning-compatible ingestion
impactweave nexus fixtures/nexus.yaml --format sarif --output impact.sarif
```

The legacy `plan` command remains supported, so existing ImpactWeave users can adopt Nexus incrementally.

## What the engine produces

| Output | Purpose |
|---|---|
| Explainable graph paths | Shows the producer → contract → consumer route used by a finding. |
| Evidence coverage | Distinguishes `observed`, `declared`, `stale`, and `unknown`; missing evidence is reviewable uncertainty. |
| Impact score | Provides a bounded triage signal, never a claim of safety. |
| Stable artifact digest | Identifies the canonical report while redacting generation time for reproducible CI snapshots. |
| Markdown | Gives reviewers a compact contract and consumer-impact table. |
| JSON | Supports automation, snapshots, and downstream integrations. |
| SARIF | Surfaces breaking findings in GitHub security and code-scanning workflows. |

## Manifest example

```yaml
strict: true
max_hops: 6
stale_after_days: 30
contracts:
  - name: orders.created
    version: "1"
    kind: event-json
    fields:
      - {path: /id, type: string, required: true}
      - {path: /total, type: number, required: true}
proposed:
  - name: orders.created
    version: "2"
    kind: event-json
    fields:
      - {path: /id, type: string, required: true}
      - {path: /total, type: integer, required: true}
      - {path: /currency, type: string, required: true}
nodes:
  - {id: checkout, kind: component}
  - {id: contract:orders.created, kind: contract}
  - {id: billing, kind: component}
graph_edges:
  - {source: checkout, target: contract:orders.created, kind: produces}
  - {source: contract:orders.created, target: billing, kind: consumes}
edges:
  - {producer: checkout, consumer: billing, contract: orders.created}
evidence:
  - producer: checkout
    consumer: billing
    contract: orders.created
    confidence: 0.98
    source: contract-test
    observed_at: "2026-08-22T12:00:00Z"
```

Graph nodes support `component`, `contract`, `tool`, `policy`, `dataset`, `deployment`, and `fixture`. Graph edges support `produces`, `consumes`, `calls`, `retrieves`, `governed_by`, `deploys`, and `derives`. The older `edges` and `evidence` fields are retained for a low-friction migration path.

## GitHub Actions

```yaml
name: impactweave
on: [pull_request]
jobs:
  impact:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install .
      - name: Analyze change impact
        run: impactweave nexus fixtures/nexus.yaml --format sarif --output impactweave.sarif
      - name: Upload impact findings
        uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: impactweave.sarif
```

Pin released versions rather than a moving branch in production workflows. A future official composite action will be added only after the manifest and artifact contracts stabilize.

## Architecture

The engine is a small, pure pipeline: validated canonical models feed the contract diff engine and a typed adjacency graph; sorted bounded traversal resolves paths; evidence coverage and policy rules produce findings; deterministic reporters emit JSON, Markdown, or SARIF. See [`docs/nexus-architecture.md`](docs/nexus-architecture.md).

## Development

```bash
pytest
ruff check .
mypy src
python -m build
```

The project targets Python 3.10+. Tests cover contract semantics, strict and permissive decisions, timezone validation, graph references, graph paths, stale evidence, deterministic digests, CLI behavior, and SARIF serialization. The core does not execute target repository code and uses safe YAML loading with input limits.

## Product roadmap

The MVP in this repository covers the canonical model, contract impact engine, typed graph paths, coverage states, deterministic artifact identity, Markdown/JSON/SARIF reporters, CLI, fixtures, and CI-quality gates. The next extensions are read-only OpenAPI, AsyncAPI, JSON Schema, SQL migration, TraceForge, Runproof, and OTel adapters. A hosted control plane is intentionally deferred until local artifacts and community workflows prove stable.

## Contributing and security

Contributions should add a focused fixture and a regression test for every new semantic rule. Please read [`CONTRIBUTING.md`](CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and [`SECURITY.md`](SECURITY.md). Security reports should not be opened as public issues.

## License

ImpactWeave Nexus is released under the [Apache License 2.0](LICENSE).
