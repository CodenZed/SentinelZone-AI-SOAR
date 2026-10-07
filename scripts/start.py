"""Single replica. Migrate the dedicated AI/SOAR DB, then bind to loopback by default."""

import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.chdir(root)

load_dotenv(root / ".env", override=False)
host = os.environ.get("AI_SOAR_BIND_ADDRESS", "127.0.0.1")
port = int(os.environ.get("AI_SOAR_PORT", "8004"))
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", str(port)])
