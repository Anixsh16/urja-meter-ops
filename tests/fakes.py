"""Synthetic protocol fixtures. These are not an exported copy of portal data."""

from copy import deepcopy

from urja.config import Settings
from urja.errors import ServiceError

TOKEN = "synthetic-test-token-at-least-24-characters"


def settings(**kwargs):
    return Settings(
        _env_file=None,
        portal_username="test@example.invalid",
        portal_password="fixture-only",
        demo_api_key=TOKEN,
        **kwargs,
    )


def row(meter_id="T001", **changes):
    value = {
        "meterId": meter_id,
        "serialNo": "SN-001",
        "make": "Fixture Electric",
        "phaseType": "single",
        "installStatus": "Installed",
        "installType": "Whole Current",
        "build": "legacy",
        "dtCode": "DT-TEST",
        "geo": {"lat": "26.9", "lng": "75.8"},
        "hierarchy": {
            level: {"code": f"{level}-TEST", "name": f"Test {level}"}
            for level in ("zone", "circle", "division", "subdivision", "substation", "feeder")
        },
    }
    value["hierarchy"]["dt"] = {"code": "DT-TEST", "name": "Test transformer"}
    value.update(changes)
    return value


def rows():
    values = [
        row(
            f"T{i:03}", serialNo=f"SN-{i:03}", installStatus="Faulty" if i % 3 == 0 else "Installed"
        )
        for i in range(1, 26)
    ]
    values[0]["hierarchy"]["dt"]["name"] = "Old transformer name"
    return values


class FakePortal:
    def __init__(self, records=None):
        self.records = records if records is not None else rows()
        self.catalog_calls = 0
        self.energy_calls = 0

    async def catalog(self):
        self.catalog_calls += 1
        return deepcopy(self.records)

    async def energy(self, meter_id, from_date=None, to_date=None):
        self.energy_calls += 1
        if meter_id == "T003":
            raise ServiceError(
                "upstream_unavailable", "The portal is temporarily unavailable.", 503
            )
        if meter_id == "T002":
            return []
        return [
            {"timestamp": "29/06/2026 00:00", "kwh": "0", "kvah": "0.00", "voltR": "230"},
            {"timestamp": "29/06/2026 00:30", "kwh": "0.42", "kvah": "0.45", "voltR": "231"},
            {"timestamp": "30/06/2026 00:00", "kwh": None, "kvah": "1.1", "voltR": "229"},
        ]
