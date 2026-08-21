# ImpactWeave

> Rehearse the blast radius of API, event, and database contract changes before merge.

ImpactWeave is a local-first Python CLI and library for **evidence-backed change-impact rehearsal**. It compares a current contract with a proposed version, resolves declared producer/consumer relationships, attaches observed evidence, and produces a deterministic report that can gate CI.

ImpactWeave is intentionally not another schema registry, data catalog, runtime proxy, or LLM governance dashboard. It focuses on one high-leverage question:

> If this contract changes, which consumers can break, how confident are we in that relationship, and should the pull request pass?

## Why it matters

Contract validators usually report structural compatibility. Lineage systems describe relationships at platform scale. ImpactWeave sits between those layers as a small repository-native rehearsal tool: it turns contract diffs into consumer-specific findings and treats missing evidence as **reviewable uncertainty** instead of silently assuming safety.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

impactweave validate fixtures/demo.yaml
impactweave plan fixtures/demo.yaml --format markdown
impactweave plan fixtures/demo.yaml --format json --output impact.json
```

The demo intentionally exits with status `1` in strict mode because the proposed event removes an enum value, tightens a numeric bound, adds a required field, and has no evidence for every relationship. That is the product behavior: uncertainty is visible before production.

## Manifest shape

```yaml
strict: true
contracts:
  - name: orders.created
    version: "1"
    kind: event-json
    fields:
      - {path: /id, type: string, required: true}
proposed:
  - name: orders.created
    version: "2"
    kind: event-json
    fields:
      - {path: /id, type: string, required: true}
edges:
  - {producer: checkout, consumer: billing, contract: orders.created}
evidence:
  - producer: checkout
    consumer: billing
    contract: orders.created
    confidence: 0.98
    source: ci-trace
    observed_at: "2026-08-20T12:00:00Z"
```

## Architecture

The core is composed of a validated canonical model, a pure contract diff engine, an adjacency-map evidence graph, an impact propagator, a policy evaluator, and deterministic JSON/Markdown reporters. There is no database, broker, network request, or model API in the MVP. See [`docs/product-and-architecture.md`](docs/product-and-architecture.md).

## CI usage

```yaml
- name: Rehearse contract impact
  run: |
    pip install .
    impactweave plan contracts/project.yaml --format json --output impact.json
```

A `pass` exits with `0`; `fail` and `review` exit with `1`. The JSON report is stable for snapshot tests because the generated timestamp is redacted from serialized output.

## Quality

```bash
ruff check .
mypy src
autopep8 --version  # optional local tool
pytest
python -m build
```

The project targets Python 3.10+ and keeps the deterministic core independent of external services. The test suite covers contract semantics, strict/permissive policies, evidence gaps, validation, and report generation.

## Roadmap

The next increments are OpenAPI and AsyncAPI importers, SQL migration parsing, SARIF annotations, evidence expiry policies, GitHub PR summaries, and adapters for protobuf/Avro. A hosted control plane is not part of the near-term roadmap.

## Security

Read [`SECURITY.md`](SECURITY.md). ImpactWeave does not execute contract content, follow remote URLs, or claim to prove runtime safety. It is an analysis and CI decision tool.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
