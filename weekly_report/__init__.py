from __future__ import annotations

# Make top-level `weekly_report` a proxy to libs/weekly_report so that
# absolute imports like `weekly_report.models` continue to resolve.
import pathlib as _pathlib
__path__ = [str(_pathlib.Path(__file__).resolve().parents[1] / 'libs' / 'weekly_report')]
