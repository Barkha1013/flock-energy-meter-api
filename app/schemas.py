"""Public response and import shapes. These are our API contract, not portal claims."""

from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class NetworkNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    node_type: str
    parent_id: str | None


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recorded_at: datetime
    consumption_kwh: float

    @field_serializer("recorded_at")
    def serialize_timestamp(self, value: datetime) -> str:
        # SQLite drops timezone metadata. Values are normalized to UTC on import.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat().replace("+00:00", "Z")


class MeterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    serial_number: str | None
    status: str | None
    meter_type: str | None
    latitude: float | None
    longitude: float | None
    installed_on: date | None
    network_node_id: str | None


class MeterDetail(MeterOut):
    network_node: NetworkNodeOut | None


class MeterPage(BaseModel):
    items: list[MeterOut]
    total: int
    limit: int
    offset: int


class ImportNode(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    node_type: str = Field(min_length=1, max_length=50)
    parent_id: str | None = None


class ImportReading(BaseModel):
    recorded_at: datetime
    consumption_kwh: float = Field(ge=0)

    @field_validator("recorded_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("recorded_at must include a timezone offset")
        return value.astimezone(timezone.utc).replace(tzinfo=None)


class ImportMeter(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    serial_number: str | None = None
    status: str | None = None
    meter_type: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    installed_on: date | None = None
    network_node_id: str | None = None
    readings: list[ImportReading] = []


class ImportBatch(BaseModel):
    network_nodes: list[ImportNode] = []
    meters: list[ImportMeter] = []


class ImportResult(BaseModel):
    nodes_upserted: int
    meters_upserted: int
    readings_upserted: int
