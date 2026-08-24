# ImpactWeave Nexus — Architecture

## Product boundary
ImpactWeave Nexus is a local-first, deterministic pre-merge decision engine for AI-enabled distributed systems. It consumes a repository manifest describing contracts, components, evidence, and change signals; computes an explainable impact graph; and emits stable JSON, Markdown, and SARIF-compatible findings suitable for GitHub Actions.

It is not an observability backend, runtime policy engine, sandbox, evaluator, or hosted control plane. Its claim is intentionally narrower: identify affected boundaries and expose uncertainty before merge, with every conclusion tied to an explicit graph path and evidence coverage state.

## Architecture

```text
Manifest / adapters
        |
        v
Canonical validated model ----> contract diff engine
        |                              |
        +----> normalized impact graph-+
                                      |
                                      v
                         path search + evidence coverage
                                      |
                                      v
                            deterministic decision engine
                                      |
                         JSON | Markdown | SARIF | exit code
```

The canonical model remains Pydantic-based and rejects unknown fields. Existing `contracts`, `proposed`, `edges`, `evidence`, and `strict` fields remain compatible. Nexus adds optional `components`, `signals`, and `policies`; empty values preserve current behavior.

## Graph semantics

Nodes are named entities such as components, contracts, tools, agent policies, datasets, or deployment artifacts. Edges are directed and typed (`produces`, `consumes`, `calls`, `retrieves`, `governed_by`, `deploys`). A changed contract creates a source node. Breadth-first traversal finds bounded paths to affected consumers. A path is evidence, not a prediction: the report states the exact edges used and whether each edge is observed, declared-only, stale, or unknown.

The engine is deterministic. Nodes and edges are canonicalized, traversal is sorted, cycles are safe, paths are bounded by `max_hops`, and generated timestamps are redacted in machine output. No repository code is executed and no network is contacted.

## Decision model

A finding contains severity, confidence, coverage state, impact path, and rationale. The policy layer can treat stale evidence and unknown edges as `review`, while known breaking changes with verified edges fail. Non-breaking changes pass unless a policy explicitly requires review. The engine never turns absence of evidence into proof of safety.

## Security and safety

Inputs are size-limited and validated. YAML uses `safe_load`. Paths and names are bounded. The engine does not execute commands, import target repositories, resolve URLs, or evaluate expressions from the manifest. Reporters escape Markdown table delimiters and SARIF strings. Optional signatures are out of MVP scope; a stable SHA-256 digest of canonical report content is included for artifact identity.

## MVP delivered in this iteration

The release elevates the existing ImpactWeave MVP into Nexus by adding typed graph nodes/edges, explicit graph paths, coverage states, deterministic impact scoring, a `nexus` command alias, SARIF output, fixtures, regression tests, CI, security policy, contributing guidance, and a polished README. Existing `validate` and `plan` commands remain supported.

## Advanced roadmap

Future adapters may import OpenAPI, AsyncAPI, JSON Schema, SQL migration plans, TraceForge bundles, Runproof cassettes, and OTel spans. A GitHub App or hosted UI is intentionally deferred until the local artifact contract is stable and community feedback validates the workflow.
