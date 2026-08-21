# ImpactWeave: product and architecture

## Product vision

ImpactWeave is a local-first, deterministic change-impact rehearsal engine for distributed systems. It turns versioned API, event, and database contract artifacts plus observed producer/consumer evidence into an explainable dependency graph. A proposed change is simulated against that graph, and the tool emits a consumer-specific blast-radius report and a CI verdict before the change reaches production.

> Make the blast radius of a contract change reviewable before the deployment.

## Problem statement

Distributed-system changes rarely fail only at the file that changed. A renamed event field, tightened response constraint, or destructive migration can break consumers that are owned by different teams and tested in different repositories. Existing contract validators can answer whether two schemas are structurally compatible, while lineage/catalog systems can describe relationships after they are known. Teams still need a small, repository-native mechanism that combines declared contracts with observed evidence, simulates a candidate change, identifies affected consumers, and fails CI with a useful explanation.

ImpactWeave deliberately does not attempt to replace a schema registry, data catalog, service mesh, or full observability platform. Its product boundary is **pre-merge impact rehearsal**.

## Target users and use cases

The primary users are platform engineers, staff engineers, API owners, event-driven architecture teams, and maintainers of data pipelines. A typical workflow is to keep a compact YAML/JSON project file in a repository, import or hand-author contract snapshots, record producer/consumer edges from CI or telemetry exporters, and run `impactweave plan` against a proposed version. The result identifies breaking changes, affected consumers, evidence confidence, and an allow/warn/fail verdict.

## User stories

| User | Story | Outcome |
|---|---|---|
| API owner | I want to compare a proposed contract against the current one. | Breaking fields and constraints are classified before merge. |
| Platform engineer | I want to attach observed consumer evidence to a graph. | The report distinguishes declared relationships from observed usage. |
| Reviewer | I want an actionable report instead of a generic schema diff. | Every finding names the consumer, path, reason, and remediation. |
| CI maintainer | I want a deterministic exit code and machine-readable output. | Pull requests can gate on a stable policy. |
| Contributor | I want to add a contract adapter without changing the core engine. | New formats can be integrated through a small plugin boundary. |

## MVP scope

The MVP implements a versioned contract model for HTTP JSON and event JSON payloads, a project manifest, explicit producer-to-consumer edges, optional observed evidence with confidence and timestamps, structural comparison for required fields/types/enums/numeric bounds, deterministic impact propagation through the graph, human-readable Markdown and machine-readable JSON reports, and CI-friendly exit codes.

The MVP also includes a safe default: if a changed contract has no consumer evidence, the report marks the confidence as unknown and can fail under a strict policy instead of silently declaring safety.

## Advanced features

The next release can add OpenAPI import, AsyncAPI import, SQL migration parsing, GitHub PR annotations, richer schema vocabulary, evidence expiry policies, and SARIF output. These are extension points, not hidden promises in the MVP.

## Future roadmap

Future work may include exporters for OpenTelemetry and OpenLineage, a small local web viewer, signed evidence bundles, organization-wide graph federation, and adapters for protobuf, Avro, GraphQL, and CDC schemas. A hosted control plane is explicitly out of scope until the local model proves useful.

## Functional requirements

The engine must validate manifests before planning, normalize contract paths deterministically, compare current and proposed versions without network access, classify findings as breaking/compatible/unknown, traverse only declared or evidence-backed edges, preserve evidence provenance in every finding, support strict and permissive policies, emit stable JSON suitable for snapshots, and return non-zero status when policy thresholds are violated.

## Non-functional requirements

The core must be deterministic, offline-first, Python 3.10+ compatible, dependency-light, testable without external services, safe against path traversal and unbounded input, and understandable from generated reports. A 1,000-node graph should be practical on a developer laptop, and the core comparison path should remain pure and side-effect free.

## System architecture

```text
manifest.yaml / contracts/*.json / evidence.jsonl
                    |
                    v
              Loader + Validator
                    |
                    v
          Canonical Contract Model
                    |
       +------------+------------+
       |                         |
       v                         v
  Contract Diff Engine      Evidence Graph
       |                         |
       +------------+------------+
                    v
             Impact Propagator
                    |
                    v
          Policy Evaluator
             /           \
            v             v
      JSON report    Markdown report
                    |
                    v
                CI exit code
```

### Components

The **models** layer defines contracts, fields, edges, evidence, findings, and reports. The **loader** layer reads YAML/JSON and JSONL while rejecting malformed or unsafe inputs. The **diff** layer compares contract snapshots and produces path-level findings. The **graph** layer indexes consumers and evidence. The **engine** combines diff and graph results into an impact plan. The **policy** layer converts findings and evidence confidence into a stable verdict. The **reporting** layer serializes results without embedding runtime-specific timestamps unless explicitly requested. The CLI is a thin adapter over these pure functions.

## Data flow

A project manifest names contract snapshots and graph edges. The loader validates and canonicalizes them. The diff engine compares each changed contract with its proposed version. The graph index resolves direct consumers and transitive dependants. The propagator attaches each breaking change to affected consumers and carries the strongest evidence status. The policy evaluator applies the configured mode. Finally, reporters serialize the same immutable report into JSON and Markdown.

## Error flow

Malformed input is rejected before comparison with a structured validation error and a non-zero CLI status. Unknown contract references are reported as graph errors rather than ignored. Unsupported schema keywords are preserved as unknown findings where possible. If strict mode encounters an unknown consumer relationship or expired evidence, it returns `review`/`fail` according to policy. No network request is performed by the core engine.

## Security model

ImpactWeave treats manifests, contracts, and evidence as untrusted data. It never executes embedded code, resolves remote URLs, follows filesystem paths outside the supplied project root, or logs raw payload values by default. Evidence identifiers and labels are bounded. JSONL processing is line-oriented with configurable size limits. The tool is an analysis engine, not an authorization mechanism and does not claim to prove runtime safety.

## Configuration and observability

Configuration is explicit in the manifest and CLI flags. The engine uses Python logging only at the boundary; core functions return structured results. `--verbose` enables diagnostic logs on stderr without changing report JSON. Stable error codes and report schema versions support automation. Future OpenTelemetry integration belongs in adapters, not in the deterministic core.

## Performance, scalability, and extensibility

Contract comparison is proportional to the number of schema nodes visited. The graph uses adjacency maps for near-linear traversal over reachable consumers. Canonical path indexing avoids repeated recursive scans. Large repositories can split manifests by domain and merge reports later. New contract formats should implement a loader that returns the canonical model; new policy modes should implement a pure evaluator; neither requires changes to the graph traversal.

## Technology decisions

ImpactWeave uses Python 3.10+, Pydantic v2 for boundary validation, PyYAML for human-authored manifests, Typer for the CLI, and pytest/Ruff/mypy for quality. It intentionally avoids a database, message broker, web server, or LLM dependency in the MVP because the primary value is deterministic local analysis.
