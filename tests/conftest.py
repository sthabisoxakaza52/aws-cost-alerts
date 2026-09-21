"""
Adds the package source directory to sys.path so tests can import
modules (notifications, sns, budget, lambda_fn, cli) directly,
without needing the package to be installed.

Place this file in the same directory as your tests, or at the project root.
Point SRC_DIR at the folder containing your .py source files.
"""

import sys
from pathlib import Path

# Adjust this to wherever your source modules live, e.g.:
#   project/
#     src/
#       notifications.py  ← SRC_DIR points here
#       sns.py
#       ...
#     tests/
#       conftest.py       ← this file
ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"

for path in (ROOT_DIR, SRC_DIR):
    if path.exists() and str(path) not in sys.path:
        sys.path.insert(0, str(path))
