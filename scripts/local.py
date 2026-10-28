"""Convenience launcher for this machine; normal installs can use .env + uvicorn."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument(
    "--config", type=Path, default=Path.home() / ".config/urja-meter-ops/credentials.json"
)
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()
values = json.loads(args.config.read_text(encoding="utf8"))
for key in ("portal_url", "portal_username", "portal_password", "demo_api_key"):
    os.environ[key.upper()] = values[key]
root = Path(__file__).resolve().parents[1]
raise SystemExit(
    subprocess.call(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "urja.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ],
        cwd=root,
    )
)
