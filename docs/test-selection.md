# ImpactWeave Safe Test Selection

## Product vision

ImpactWeave helps a team answer one operational question before merge: **which tests are justified by this change, and when is it safer to run the full suite?** It is a local-first decision engine, not a hosted test runner. The engine produces a plan; the caller decides how and where to execute the commands.

The project is intentionally conservative. A small subset is marked safe only when every effective changed path maps to a declared test ownership contract, no tracked safety-sensitive path changed, the policy allows the selected count, and no required evidence is stale or missing. Otherwise the verdict is `full_suite` and the report explains why.

## Target users and use cases

ImpactWeave targets maintainers of polyglot repositories, platform engineers maintaining CI workflows, and teams with expensive or flaky test suites that need a transparent alternative to opaque predictive selection. Typical workflows include previewing a PR test plan locally, generating a SARIF artifact in GitHub Actions, reviewing why a test was selected or skipped, and gradually adding ownership mappings without adopting a remote service.

## MVP requirements

| Area | Requirement | Status |
|---|---|---|
| Change input | Accept explicit relative paths or a Git `base...head` diff | Implemented |
| Test contract | Declare stable test IDs, argv tokens, path globs, tags, and estimates | Implemented |
| Safety policy | Support ignored paths, tracked paths, always-run targets, maximum subset size, and fallback policy | Implemented |
| Evidence | Consume optional fresh observations without storing raw test output | Implemented |
| Decision | Return `safe_subset`, `full_suite`, or `review` with reasons | Implemented |
| Explainability | Include matched paths, evidence sources, commands, and stable digest | Implemented |
| Outputs | JSON, Markdown, SARIF 2.1.0, CLI exit semantics | Implemented |
| Compatibility | Preserve Nexus contract-impact commands and manifest fields | Implemented |
| Execution | Run target commands, install dependencies, or checkout code | Deliberately not implemented |
| Hosted service | Accounts, database, telemetry, or remote cache | Deliberately not implemented |

## Manifest contract

A test target is declarative. `command` is an argv array rather than a shell string, so the plan cannot introduce shell interpolation. A target with `always: true` does not need a path map. Every other target must declare one or more globs. `tracked_paths` are files for which the mapping is not considered sufficient, such as lockfiles, build configuration, or CI definitions.

```yaml
tests:
  - id: unit.checkout
    command: [pytest, tests/checkout, -q]
    paths: [src/checkout/**, tests/checkout/**]
    tags: [unit, fast]
    estimated_seconds: 45
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

`safe_subset` means the plan is justified by the supplied contract and policy; it does not claim the selected tests prove the change is safe. `full_suite` means every declared target is selected because the engine found a tracked path, an unmapped path, too many selected tests, or no test targets. `review` is reserved for a caller that explicitly disables fallback and leaves no test target justifiable. The planner never silently turns uncertainty into a skip.

Ignored paths are removed from the effective diff, but always-run tests remain selected. An ignored-only documentation change therefore produces a minimal plan containing the always-run targets. A changed lockfile or CI file forces `full_suite` even if other mappings look precise.

## Data flow

```text
explicit paths or Git diff
          |
          v
normalize + reject unsafe paths
          |
          v
apply ignored-path policy
          |
          +--> match declared ownership globs
          +--> match fresh observations
          +--> detect tracked/unmapped paths
          |
          v
build per-test decisions
          |
          v
safe subset OR full-suite fallback
          |
          v
canonical JSON + digest -> Markdown / SARIF / CI artifact
```

The Git integration reads only `git diff --name-only`. It does not execute repository commands, inspect source contents, checkout a ref, or run tests. The test commands are emitted as data for a downstream runner.

## Security model

The input boundary rejects absolute paths, NUL bytes, and traversal outside the repository. Git refs that begin with `-` are rejected and passed as a single argument to `subprocess.run`; no shell is used. YAML is loaded with `yaml.safe_load` and bounded by the existing manifest size limit. Test commands remain argv arrays and are never executed by ImpactWeave. Reports contain paths and command metadata but never test stdout, secrets, environment variables, or network payloads.

The planner is not a sandbox. If a caller later executes commands from a generated plan, that execution belongs in the caller's isolated CI job with normal permissions, timeouts, network restrictions, and secret policy. A mapping is an engineering contract, not proof of semantic completeness.

## Performance and scalability

Planning is linear in the number of changed paths multiplied by the number of path patterns, with deterministic sorting and bounded manifest sizes. Git diff output is capped at 2 MB. The engine does not require a database or remote cache, so a plan can run on a developer laptop or a short-lived CI runner. Future adapters can precompute ownership indexes without changing the public decision model.

## Extensibility

Adapters may translate Python coverage, JavaScript coverage, OpenAPI/AsyncAPI/JSON Schema changes, SQL migrations, or monorepo graphs into `TestObservation` and `TestTarget` records. Each adapter must be optional, deterministic, bounded, and tested with positive and negative fixtures. The core will not load arbitrary code or policy expressions from a manifest.

## Roadmap

The next release can add a first-party coverage adapter and a `--explain` text mode. A later release may add OpenAPI/AsyncAPI/JSON Schema adapters, a GitHub Checks summary, and a benchmark corpus that measures precision, recall, skipped-test safety, and planning latency. Remote learning, hosted analytics, and automatic command execution remain outside the core until real users demonstrate a need and a safe trust model.
