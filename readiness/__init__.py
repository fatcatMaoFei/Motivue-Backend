from __future__ import annotations

# Proxy top-level `readiness` package to libs/readiness_engine so legacy imports
# like `from readiness.constants import ...` continue to work.
import pathlib as _pathlib
__path__ = [str(_pathlib.Path(__file__).resolve().parents[1] / 'libs' / 'readiness_engine')]
