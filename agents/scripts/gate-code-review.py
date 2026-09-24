#!/usr/bin/env python3
"""Délègue au hook canonique agents/hooks/gate-code-review/hook.py."""

from __future__ import annotations

import runpy
from pathlib import Path

_CANON = (
    Path(__file__).resolve().parents[2]
    / "agents"
    / "hooks"
    / "gate-code-review"
    / "hook.py"
)
runpy.run_path(str(_CANON), run_name="__main__")
