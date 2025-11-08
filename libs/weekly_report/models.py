from __future__ import annotations

# Proxy models to the shared core-domain models so that existing
# imports like `from weekly_report.models import ChartSpec` continue to work
# under the refactored layout.
from libs.core_domain.models import *  # noqa: F401,F403

