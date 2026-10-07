"""Same-origin standalone UI + backend for native development, after migrations/build."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from fastapi.staticfiles import StaticFiles
from app.config import ROOT
from app.main import create_app

app = create_app()
app.mount("/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="web")
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("WEB_PORT", "8080")))
