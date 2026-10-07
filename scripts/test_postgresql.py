"""Opt-in destructive tests ONLY against the named dedicated disposable AI/SOAR test DB.
Provision it yourself with an independent test owner; URL is read from environment.
"""

import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
url = os.environ.get("TEST_DATABASE_URL", "")
try:
    parsed = make_url(url)
    safe = parsed.get_backend_name() == "postgresql" and parsed.database == "sentinelzone_ai_soar_test"
except Exception:
    safe = False
if not safe:
    raise SystemExit("NOT RUN: set TEST_DATABASE_URL to a disposable sentinelzone_ai_soar_test PostgreSQL database")
# The URL and its credentials are never passed in command-line arguments or printed.
raise SystemExit(subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short"], cwd=root).returncode)
