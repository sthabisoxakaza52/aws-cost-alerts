"""
Pytest configuration and shared test fixtures for aws-cost-alerts.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

ROOT_DIR = Path(__file__).parent.parent
PACKAGE_DIR = ROOT_DIR / "cost_alerts"

for path in (ROOT_DIR, PACKAGE_DIR):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))


def make_session(client_map):
    """Utility helper to build mock boto3 sessions."""
    session = MagicMock()
    session.client.side_effect = lambda svc, **kw: client_map[svc]
    return session
