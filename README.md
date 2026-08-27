# ImpactWeave

> **Know what your change can break. Run only what you can justify.**

ImpactWeave is a **local-first, deterministic change-impact and safe test-selection engine** for polyglot repositories. It turns a Git diff and a versioned test ownership contract into an explainable plan: a justified subset, a conservative full-suite fallback, or an explicit review state.

It does not execute test commands, call an LLM, upload source code, require a database, or depend on a hosted control plane. It produces portable JSON, Markdown, SARIF, and CI-friendly exit semantics that a downstream runner can consume.

## Why it exists

CI systems often have to choose between running an expensive full suite on every change or skipping tests with assumptions that are difficult to review. Existing approaches can be tied to a monorepo graph, historical coverage service, or opaque prediction. ImpactWeave makes the decision contract explicit and fail-safe: unknown or high-risk changes widen the plan instead of silently narrowing it.

## What is implemented in 0.3

| Capability | Status |
|---|---|
| Git `base...head` diff or explicit changed paths | Implemented |
| Relative-path normalization and traversal rejection | Implemented |
| Declarative test targets with argv arrays, path globs, tags, and estimates | Implemented |
| Always-run, ignored-paths, tracked-paths, and max-subset policy | Implemented |
| Fresh optional observations without raw test output | Implemented |
| `safe_subset`, `full_suite`, and `review` verdict semantics | Implemented |
| Per-test reason, matched paths, evidence sources, and artifact digest | Implemented |
| JSON, Markdown, SARIF 2.1.0, and CLI | Implemented |
| Existing Nexus contract-impact engine | Preserved |
| Coverage/OpenAPI/AsyncAPI/JSON Schema adapters | Roadmap |
| Remote service, model ranking, or automatic command execution | Out of scope for core |

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

# Plan from explicit paths; this command never runs the emitted tests.
impactweave test-plan fixtures/test-plan.yaml \
  --changed src/checkout/cart.py \
  --format markdown

# Plan directly from a Git range.
impactweave test-plan fixtures/test-plan.yaml \
  --repo . --base HEAD~1 --head HEAD \
  --format sarif --output impactweave.sarif
```

The checked-in fixture demonstrates a safe subset for a checkout change, an always-run lint target, and full-suite fallback for a lockfile or unmapped path. The test planner returns exit code `1` only for `review`; `safe_subset` and `full_suite` are valid decisions and return `0`.

## Test ownership contract

A target uses an argv array rather than a shell string. This prevents ImpactWeave from introducing shell interpolation and makes the plan portable to another runner.

```yaml
tests:
  - id: unit.checkout
    command: [pytest, tests/checkout, -q]
    paths: [src/checkout/**, tests/checkout/**]
    tags: [unit, fast]
    estimated_seconds: 45
  - id: contract.api
    command: [pytest, tests/contracts, -q]
    paths: [contracts/**, schemas/**, src/api/**]
  - id: lint
    command: [ruff, check, .]
    always: true

test_policy:
  tracked_paths: [pyproject.toml, uv.lock, .github/workflows/**]
  ignored_paths: [docs/**, "**/*.md"]
  fallback_on_unknown: true
  max_selected: 20
  stale_after_days: 30
```

## Decision semantics

`safe_subset` means every effective changed path is justified by a target mapping or a fresh observation, and the policy permits the resulting subset. It is not a proof that the selected tests cover every semantic consequence of the change.

`full_suite` means the planner selected every declared target because a tracked path changed, a path was unmapped, the subset exceeded the policy limit, or the manifest contained no targets. `review` is reserved for a caller that disables fallback and leaves no target justifiable. The engine never silently treats uncertainty as a skip.

## GitHub Actions

```yaml
name: ImpactWeave test plan

on: [pull_request]

permissions:
  contents: read

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install .
      - name: Build conservative test plan
        run: >-
          impactweave test-plan fixtures/test-plan.yaml
          --base "${{ github.event.pull_request.base.sha }}"
          --head "${{ github.event.pull_request.head.sha }}"
          --format sarif --output impactweave.sarif
      - name: Upload plan findings
        if: always()
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: impactweave.sarif
```

ImpactWeave reports the plan; the caller owns execution, sandboxing, timeouts, secrets, and sharding. Pin released versions in production workflows rather than tracking a moving branch.

## Existing Nexus engine

The original contract-impact engine remains available:

```bash
impactweave validate fixtures/nexus.yaml
impactweave nexus fixtures/nexus.yaml --format markdown --output impact.md
impactweave nexus fixtures/nexus.yaml --format sarif --output impact.sarif
```

Nexus answers which consumers can be affected by a contract change. The test planner answers which test commands deserve execution for a code change. They share the same versioned manifest so teams can adopt either surface incrementally.

## Architecture and security

```text
explicit paths or Git diff
          -> normalize and reject unsafe paths
          -> apply ignored-path policy
          -> match test ownership and fresh observations
          -> detect tracked or unmapped paths
          -> safe subset or full-suite fallback
          -> canonical digest -> JSON / Markdown / SARIF
```

The core is pure after input loading. YAML uses safe parsing and bounded input sizes. Git is called only as `git diff --name-only` with argv and a timeout. Absolute paths, NUL bytes, traversal, and option-like Git refs are rejected. Test commands remain data and are never executed. Reports contain no environment values or test output.

Read [`docs/test-selection.md`](docs/test-selection.md) for the product contract and [`docs/architecture-0.3.md`](docs/architecture-0.3.md) for component boundaries, error flow, performance, scalability, testing, and roadmap details. Read [`SECURITY.md`](SECURITY.md) before reporting a vulnerability.

## Development

```bash
pip install -e '.[dev]'
ruff check .
mypy src
pytest
python -m build
```

The suite includes 28 tests with a coverage threshold above 90%, temporary Git integration, deterministic artifact checks, policy fallback cases, and report serialization. Every new rule should add a positive and negative fixture plus a focused regression test.

## Roadmap

The next release will prioritize coverage.py and LCOV adapters, an explicit `--explain` mode, richer GitHub Checks summaries, and OpenAPI/AsyncAPI/JSON Schema impact adapters. A later release may add an indexed matcher and JUnit history import. Remote learning, hosted analytics, and automatic command execution remain outside the trust-critical core until a safe, reviewable contract exists.

## License

Apache-2.0. See [`LICENSE`](LICENSE).
