#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Wrapper: moved from project root to readiness/ for organization.
# Original script remains compatible; this is the canonical location now.

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path to import dynamic_model as originally written
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reuse the original implementation
from personalization_em_demo import *  # type: ignore

