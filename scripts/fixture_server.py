"""Offline browser-test server using explicit synthetic records, never live credentials."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.fakes import FakePortal, settings  # noqa: E402
from urja.main import create_app  # noqa: E402
from urja.service import MeterService  # noqa: E402

config = settings()
app = create_app(config, MeterService(FakePortal(), config))
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8011)
