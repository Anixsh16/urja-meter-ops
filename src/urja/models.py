from datetime import datetime
from decimal import Decimal
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    fetched_at: datetime
    cache: str
    age_seconds: int = 0
    warnings: list[str] = Field(default_factory=list)


class Result(BaseModel, Generic[T]):
    data: T
    meta: Meta


class NetworkSegment(BaseModel):
    level: str
    code: str | None
    name: str | None


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Meter(BaseModel):
    id: str
    serial_number: str | None = None
    manufacturer: str | None = None
    phase: str | None = None
    status: str | None = None
    installation_type: str | None = None
    portal_build: str | None = None
    transformer_code: str | None = None
    location: Coordinates | None = None
    hierarchy: list[NetworkSegment] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MeterPage(BaseModel):
    items: list[Meter]
    total: int
    page: int
    page_size: int
    total_pages: int


class Reading(BaseModel):
    timestamp: datetime
    source_timestamp: str
    kwh: Decimal | None = None
    kvah: Decimal | None = None
    voltage_r: Decimal | None = None


class Consumption(BaseModel):
    meter_id: str
    kind: str = "cumulative_register"
    timezone: str
    timezone_basis: str = "Configured assumption; portal timestamps have no offset"
    readings: list[Reading]
    units: dict[str, str] = {"kwh": "kWh", "kvah": "kVAh", "voltage_r": "V"}


class NetworkNode(BaseModel):
    id: str
    parent_id: str | None
    level: str
    code: str | None
    name: str
    aliases: list[str] = Field(default_factory=list)
    meter_count: int
    child_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class NodePage(BaseModel):
    items: list[NetworkNode]
    total: int


class ErrorInfo(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorInfo
