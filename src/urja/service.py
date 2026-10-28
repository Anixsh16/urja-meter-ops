import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from urja.cache import TTLCache
from urja.config import Settings
from urja.errors import ServiceError, protocol_error
from urja.models import (
    Consumption,
    Coordinates,
    Meter,
    MeterPage,
    NetworkNode,
    NetworkSegment,
    Reading,
    Result,
)

LEVELS = ("zone", "circle", "division", "subdivision", "substation", "feeder", "dt")


def text(value):
    if value is None or str(value).strip() == "":
        return None
    return str(value).strip()


def normalize_meter(row: dict) -> Meter:
    meter_id = row.get("meterId")
    if not isinstance(meter_id, str) or not meter_id:
        raise protocol_error()
    warnings = []
    location = None
    geo = row.get("geo")
    try:
        if isinstance(geo, dict) and geo.get("lat") is not None and geo.get("lng") is not None:
            location = Coordinates(latitude=geo["lat"], longitude=geo["lng"])
        else:
            warnings.append("Coordinates are missing.")
    except (ValueError, ValidationError):
        warnings.append("Invalid coordinates were excluded; no location was inferred.")
    hierarchy = []
    source = row.get("hierarchy")
    if not isinstance(source, dict):
        source = {}
    for level in LEVELS:
        segment = source.get(level)
        segment = segment if isinstance(segment, dict) else {}
        code, name = text(segment.get("code")), text(segment.get("name"))
        if not code:
            warnings.append(f"Missing {level} code; parent relationship is unresolved.")
        hierarchy.append(NetworkSegment(level=level, code=code, name=name))
    if text(row.get("dtCode")) != hierarchy[-1].code:
        warnings.append("Transformer code differs between meter and hierarchy records.")
    return Meter(
        id=meter_id,
        serial_number=text(row.get("serialNo")),
        manufacturer=text(row.get("make")),
        phase=text(row.get("phaseType")),
        status=text(row.get("installStatus")),
        installation_type=text(row.get("installType")),
        portal_build=text(row.get("build")),
        transformer_code=text(row.get("dtCode")),
        location=location,
        hierarchy=hierarchy,
        warnings=warnings,
    )


@dataclass
class Snapshot:
    meters: list[Meter]
    by_id: dict[str, Meter]
    nodes: dict[str, NetworkNode]
    members: dict[str, set[str]]
    warnings: list[str]


def build_snapshot(rows: list[dict]) -> Snapshot:
    meters = sorted((normalize_meter(row) for row in rows), key=lambda meter: meter.id)
    if len({meter.id for meter in meters}) != len(meters):
        raise ServiceError(
            "duplicate_meter_id", "Portal export contains ambiguous duplicate meter IDs."
        )
    node_data, memberships, variants = {}, defaultdict(set), defaultdict(set)
    for meter in meters:
        parent = None
        for segment in meter.hierarchy:
            if not segment.code:
                parent = None  # A missing level must not create an invented ancestor edge.
                continue
            identity = f"{parent or 'root'}|{segment.level}|{segment.code}"
            node_id = segment.level + "_" + hashlib.sha256(identity.encode()).hexdigest()[:20]
            if node_id not in node_data:
                node_data[node_id] = {"parent": parent, "segment": segment, "names": set()}
            if segment.name:
                node_data[node_id]["names"].add(segment.name)
            memberships[node_id].add(meter.id)
            variants[(segment.level, segment.code)].add(node_id)
            parent = node_id
    nodes = {}
    for node_id, data in node_data.items():
        segment = data["segment"]
        names = sorted(data["names"])
        warnings = []
        if len(names) > 1:
            warnings.append("Source uses multiple names for this code and parent.")
        if len(variants[(segment.level, segment.code)]) > 1:
            warnings.append(
                "Source places this code under multiple parent paths; variants are preserved."
            )
        if data["parent"] is None and segment.level != "zone":
            warnings.append("Parent path is incomplete.")
        nodes[node_id] = NetworkNode(
            id=node_id,
            parent_id=data["parent"],
            level=segment.level,
            code=segment.code,
            name=names[0] if names else segment.code,
            aliases=names[1:],
            meter_count=len(memberships[node_id]),
            warnings=warnings,
        )
    for node in nodes.values():
        if node.parent_id:
            nodes[node.parent_id].child_count += 1
    warning_count = sum(bool(node.warnings) for node in nodes.values())
    warnings = (
        [f"{warning_count} hierarchy nodes have source inconsistencies."] if warning_count else []
    )
    bad_meters = sum(bool(meter.warnings) for meter in meters)
    if bad_meters:
        warnings.append(
            f"{bad_meters} meters have missing or inconsistent fields; inspect meter warnings."
        )
    return Snapshot(meters, {m.id: m for m in meters}, nodes, dict(memberships), warnings)


def decimal_or_none(value, field: str, warnings: set[str]):
    if value is None or str(value).strip() in {"", "-", "--", "N/A"}:
        return None
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            raise InvalidOperation
        return number
    except InvalidOperation:
        warnings.add(f"Invalid {field} values were returned as null.")
        return None


def normalize_energy(rows: list[dict], meter_id: str, timezone: str):
    warnings = {
        "Timezone is configured, not supplied by the portal; readings are cumulative registers."
    }
    readings = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("timestamp"), str):
            raise protocol_error()
        raw_timestamp = row["timestamp"]
        try:
            timestamp = datetime.strptime(raw_timestamp, "%d/%m/%Y %H:%M").replace(
                tzinfo=ZoneInfo(timezone)
            )
        except ValueError as exc:
            raise protocol_error() from exc
        if timestamp in seen:
            warnings.add(
                "Duplicate timestamps are preserved; no aggregate consumption was inferred."
            )
        seen.add(timestamp)
        readings.append(
            Reading(
                timestamp=timestamp,
                source_timestamp=raw_timestamp,
                kwh=decimal_or_none(row.get("kwh"), "kWh", warnings),
                kvah=decimal_or_none(row.get("kvah"), "kVAh", warnings),
                voltage_r=decimal_or_none(row.get("voltR"), "voltage", warnings),
            )
        )
    readings.sort(key=lambda reading: reading.timestamp)
    if any(
        a.kwh is not None and b.kwh is not None and b.kwh < a.kwh
        for a, b in zip(readings, readings[1:])
    ):
        warnings.add("Register decreases detected; resets/rollovers are not converted to usage.")
    return Consumption(meter_id=meter_id, timezone=timezone, readings=readings), sorted(warnings)


class MeterService:
    def __init__(self, portal, settings: Settings, cache=None):
        self.portal = portal
        self.settings = settings
        self.cache = cache or TTLCache(settings.cache_entries)

    async def snapshot(self):
        async def load():
            return build_snapshot(await self.portal.catalog())

        snapshot, meta = await self.cache.get("catalog", self.settings.catalog_ttl, load)
        meta.warnings = snapshot.warnings.copy()
        return snapshot, meta

    async def meters(self, q, page, page_size, status=None, node_id=None):
        snapshot, meta = await self.snapshot()
        items = snapshot.meters
        if q:
            term = q.casefold()
            items = [
                m
                for m in items
                if term in m.id.casefold() or term in (m.serial_number or "").casefold()
            ]
        if status:
            items = [m for m in items if (m.status or "").casefold() == status.casefold()]
        if node_id:
            if node_id not in snapshot.nodes:
                raise ServiceError("not_found", "Network node not found.", 404)
            items = [m for m in items if m.id in snapshot.members[node_id]]
        total = len(items)
        return Result(
            data=MeterPage(
                items=items[(page - 1) * page_size : page * page_size],
                total=total,
                page=page,
                page_size=page_size,
                total_pages=math.ceil(total / page_size),
            ),
            meta=meta,
        )

    async def meter(self, meter_id):
        snapshot, meta = await self.snapshot()
        if meter_id not in snapshot.by_id:
            raise ServiceError("not_found", "Meter not found.", 404)
        return Result(data=snapshot.by_id[meter_id], meta=meta)

    async def consumption(self, meter_id, from_date, to_date):
        await self.meter(meter_id)

        async def load():
            rows = await self.portal.energy(meter_id, from_date, to_date)
            return normalize_energy(rows, meter_id, self.settings.portal_timezone)

        key = ("energy", meter_id, from_date, to_date)
        (data, warnings), meta = await self.cache.get(key, self.settings.energy_ttl, load)
        # Enforce the documented window even if the portal ignores query parameters.
        data = data.model_copy(
            update={
                "readings": [
                    r
                    for r in data.readings
                    if (not from_date or r.timestamp.date() >= from_date)
                    and (not to_date or r.timestamp.date() <= to_date)
                ]
            }
        )
        meta.warnings = warnings.copy()
        return Result(data=data, meta=meta)
