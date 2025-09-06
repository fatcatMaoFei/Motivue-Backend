#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Wrapper: moved from project root to readiness/ for organization.

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from personalization_em_demo_woman import *  # type: ignore

