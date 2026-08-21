# Contributing

ImpactWeave keeps its deterministic core small. Before opening a pull request, install the development extras and run `ruff check .`, `mypy src`, `pytest`, and `python -m build`.

New contract formats should enter through a loader that produces the canonical models in `models.py`. New policy behavior should be a pure function with explicit tests for pass, fail, and unknown evidence. Reports must remain stable and must not include secrets or nondeterministic timestamps unless a feature explicitly requires them.

Please include a focused test, update the relevant documentation, and explain compatibility implications in the pull request. Security-sensitive reports belong in the private reporting channel described in `SECURITY.md`.
