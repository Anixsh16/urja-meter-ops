"""Regenerate the checked-in public API description without any credentials/network."""

import json
from pathlib import Path

from urja.main import create_app

target = Path(__file__).resolve().parents[1] / "openapi.json"
target.write_text(
    json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n", encoding="utf8"
)
print("Exported openapi.json")
