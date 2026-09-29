"""Start the browser-test API with an isolated, disposable database.

Run with apps/api/.venv/bin/python. Never touches the developer database.
"""
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "apps" / "api"

with TemporaryDirectory(prefix="leadflow-e2e-") as directory:
    os.environ.update(
        LEADFLOW_DATABASE_URL=f"sqlite:///{Path(directory) / 'test.db'}",
        LEADFLOW_ENVIRONMENT="development",
        LEADFLOW_BOOTSTRAP_PASSWORD="e2e-only-admin-password",
        LEADFLOW_ALLOWED_ORIGINS="http://127.0.0.1:4173,http://127.0.0.1:4174",
    )
    os.chdir(API)
    sys.path.insert(0, str(API))
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "app.cli", "bootstrap-admin", "--login-id", "e2e-admin", "--name", "테스트 관리자"], check=True)
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=18000, log_level="warning")
