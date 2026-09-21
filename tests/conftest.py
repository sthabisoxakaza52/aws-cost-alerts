"""
Pytest configuration for aws-cost-alerts.
Ensures repository root and package source are accessible to test runners.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent
PACKAGE_DIR = ROOT_DIR / "cost_alerts"

for path in (ROOT_DIR, PACKAGE_DIR):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))
