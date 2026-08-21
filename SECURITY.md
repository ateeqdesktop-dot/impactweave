# Security policy

## Scope

ImpactWeave analyzes contract metadata and evidence. It does not execute contract content, invoke remote URLs, or enforce runtime authorization. Do not treat a passing report as proof that a deployment is safe.

## Supported versions

The `main` branch and the latest tagged release receive security fixes during the early development period.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting for the repository and include a concise reproduction, affected version, impact, and suggested mitigation. Do not include real credentials, customer payloads, or private production data.

## Defensive design

The loader uses safe YAML parsing, bounded file sizes, strict Pydantic models, no dynamic imports, no shell execution, and no network access. Reports avoid raw payload capture. These controls reduce common risks but do not make arbitrary untrusted files harmless at the operating-system level.
