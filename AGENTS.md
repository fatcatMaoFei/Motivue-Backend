# Repository Guidelines

## Project Structure & Module Organization
- Location: `PycharmProject/IBF/`
- Main module: `CPT.py` — Bayesian readiness calculator (current focus).
- Artifacts: generated `*.csv` and `*.png` may appear in the same directory.
- Optional: local virtualenv `ven/` (do not commit), IDE files `.idea/` (ignore).

## Build, Test, and Development Commands
- Create env (Windows): `python -m venv ven` then `ven\Scripts\activate`.
- Install deps (minimum): `pip install numpy pandas`.
- Run locally: `python CPT.py`.
- Lint/format (optional): `pip install black ruff` then `black . && ruff check .`.

## Coding Style & Naming Conventions
- Python ≥ 3.11; 4-space indentation; follow PEP 8.
- Naming: `snake_case` (functions/vars), `PascalCase` (classes), `UPPER_SNAKE_CASE` (constants).
- Prefer type hints and concise docstrings for public APIs; keep the file single-responsibility.

## Testing Guidelines
- If adding tests, place them as `test_*.py` next to `CPT.py` and run with `pytest -q`.
- Focus on deterministic unit tests around Bayesian update logic and score calculation.

## Commit & Pull Request Guidelines
- Commits: Conventional style — `feat:`, `fix:`, `refactor:`, `docs:`, `test:` (e.g., `fix(cpt): normalize transition probs`).
- PRs: include purpose, minimal reproduction or sample inputs, and before/after readiness outputs if applicable.

## Core Programming Rules (Memory)
- KISS: choose the simplest workable solution; avoid over-engineering.
- YAGNI: implement only what’s required now; no speculative features.
- SOLID (brief): Single Responsibility; Open/Closed; Liskov Substitution; Interface Segregation; Dependency Inversion.

