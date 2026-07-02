#!/usr/bin/env python3
"""Backward-compatible launcher for the oss-version skill."""

import sys
from pathlib import Path

# Add skill root to path so oss_version package is importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from oss_version import main

raise SystemExit(main())
