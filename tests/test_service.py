import asyncio
from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from tests.fakes import FakePortal, row, settings
from urja.cache import TTLCache
from urja.errors import ServiceError
from urja.service import MeterService, build_snapshot, normalize_energy, normalize_meter


def test_normalization_preserves_source_and_zero_coordinates():
    meter = normalize_meter(row(geo={"lat": "0", "lng": "0"}))
    assert meter.location.latitude == 0
    assert meter.location.longitude == 0
    assert meter.serial_number == "SN-001"
    assert meter.hierarchy[-1].code == "DT-TEST"


@pytest.mark.parametrize(
    "geo", [None, {}, {"lat": "NaN", "lng": 75}, {"lat": 91, "lng": 75}, {"lat": 26, "lng": 181}]
)
def test_invalid_geo_is_visible_not_fabricated(geo):
    meter = normalize_meter(row(geo=geo))
    assert meter.location is None
    assert meter.warnings


def test_hierarchy_aliases_and_conflicting_parents_remain_visible():
    first = row("ONE")
    alias = deepcopy(first)
    alias["meterId"] = "TWO"
    alias["hierarchy"]["dt"]["name"] = "Legacy spelling"
    variant = deepcopy(first)
    variant["meterId"] = "THREE"
    variant["hierarchy"]["feeder"]["code"] = "OTHER"
    snapshot = build_snapshot([first, alias, variant])
    transformers = [n for n in snapshot.nodes.values() if n.level == "dt"]
    assert len(transformers) == 2
    assert sorted(n.meter_count for n in transformers) == [1, 2]
    assert any(n.aliases for n in transformers)
    assert all(n.warnings for n in transformers)
    assert len({n.id for n in transformers}) == 2
    assert set(snapshot.members[transformers[0].id]) <= {"ONE", "TWO", "THREE"}


def test_missing_level_does_not_invent_edge():
    value = row()
    del value["hierarchy"]["feeder"]
    snapshot = build_snapshot([value])
    dt = next(n for n in snapshot.nodes.values() if n.level == "dt")
    assert dt.parent_id is None
    assert "Parent path is incomplete." in dt.warnings


def test_ids_are_order_independent():
    a, b = row("A"), row("B")
    assert build_snapshot([a, b]).nodes == build_snapshot([b, a]).nodes


@pytest.mark.parametrize("records", [[row("A"), row("A")], [{"serialNo": "missing id"}]])
def test_ambiguous_catalog_is_rejected(records):
    with pytest.raises(ServiceError):
        build_snapshot(records)


def test_energy_precision_zero_missing_and_timestamp_assumption():
    energy, warnings = normalize_energy(
        [
            {"timestamp": "29/06/2026 00:30", "kwh": "0.420000001", "kvah": "NaN"},
            {"timestamp": "29/06/2026 00:00", "kwh": "0", "kvah": None},
        ],
        "T001",
        "Asia/Kolkata",
    )
    assert energy.readings[0].kwh == 0
    assert energy.readings[1].kwh == Decimal("0.420000001")
    assert energy.readings[1].kvah is None
    assert energy.readings[0].timestamp.isoformat().endswith("+05:30")
    assert energy.readings[0].source_timestamp == "29/06/2026 00:00"
    assert any("Invalid" in w for w in warnings)
    assert energy.model_dump(mode="json")["readings"][1]["kwh"] == "0.420000001"


def test_duplicate_and_decreasing_registers_flagged():
    energy, warnings = normalize_energy(
        [
            {"timestamp": "29/06/2026 00:00", "kwh": "8"},
            {"timestamp": "29/06/2026 00:00", "kwh": "7"},
        ],
        "T001",
        "Asia/Kolkata",
    )
    assert len(energy.readings) == 2
    assert any("Duplicate" in w for w in warnings)
    assert any("decreases" in w for w in warnings)


@pytest.mark.parametrize("records", [[{}], [{"timestamp": "not-a-date"}], [None]])
def test_invalid_energy_contract_fails(records):
    with pytest.raises(ServiceError):
        normalize_energy(records, "T001", "Asia/Kolkata")


async def test_cache_singleflight_expiry_and_failed_refresh():
    clock = [0.0]
    cache = TTLCache(2, clock=lambda: clock[0])
    calls = []

    async def load():
        calls.append(1)
        await asyncio.sleep(0)
        return "fresh"

    results = await asyncio.gather(*(cache.get("same", 10, load) for _ in range(5)))
    assert len(calls) == 1
    assert [r[1].cache for r in results].count("hit") == 4
    clock[0] = 11

    async def fail():
        raise ServiceError("upstream_unavailable", "Unavailable", 503)

    with pytest.raises(ServiceError):
        await cache.get("same", 10, fail)
    assert "same" not in cache.entries
    await cache.get("same", 10, load)
    assert len(calls) == 2
    await cache.get("second", 10, load)
    await cache.get("third", 10, load)
    assert len(cache.entries) == 2


async def test_search_pagination_status_node_filter_and_source_cache():
    portal = FakePortal()
    service = MeterService(portal, settings())
    first = await service.meters("", 1, 20)
    second = await service.meters("", 2, 20)
    assert first.data.total == 25 and len(second.data.items) == 5
    assert not {m.id for m in first.data.items} & {m.id for m in second.data.items}
    assert (await service.meters("sn-001", 1, 20)).data.items[0].id == "T001"
    assert (await service.meters("", 1, 20, "faulty")).data.total == 8
    assert portal.catalog_calls == 1
    snap, _ = await service.snapshot()
    node_id = next(iter(snap.nodes))
    assert (await service.meters("", 1, 100, node_id=node_id)).data.total == 25
    with pytest.raises(ServiceError):
        await service.meters("", 1, 20, node_id="missing")


async def test_date_filter_is_inclusive_and_ignoring_upstream_cannot_bypass_it():
    service = MeterService(FakePortal(), settings())
    result = await service.consumption("T001", date(2026, 6, 29), date(2026, 6, 29))
    assert len(result.data.readings) == 2
    assert all(r.timestamp.date() == date(2026, 6, 29) for r in result.data.readings)
    assert result.meta.cache == "miss"
    assert (
        await service.consumption("T001", date(2026, 6, 29), date(2026, 6, 29))
    ).meta.cache == "hit"


def test_reused_codes_cannot_create_hierarchy_cycles():
    value = row()
    for segment in value["hierarchy"].values():
        segment["code"] = "SAME-CODE"
    snapshot = build_snapshot([value])
    assert len(snapshot.nodes) == 7
    for node in snapshot.nodes.values():
        visited = set()
        current = node
        while current is not None:
            assert current.id not in visited
            visited.add(current.id)
            current = snapshot.nodes.get(current.parent_id)
