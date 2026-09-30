"""Stable public response schemas, normalized from the portal's source field names."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class NetworkNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    node_type: str
    parent_id: str | None


class MeterOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    serial_number: str
    make: str
    phase_type: str
    install_status: str
    install_type: str
    build: str
    dt_code: str
    latitude: float
    longitude: float


class MeterDetail(MeterOut):
    network_hierarchy: list[NetworkNodeOut]


class TransformerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    feeder_code: str
    capacity_kva: float | None


class MeterPage(BaseModel):
    items: list[MeterOut]
    total: int
    limit: int
    offset: int


class TransformerPage(BaseModel):
    items: list[TransformerOut]
    total: int
    limit: int
    offset: int


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    recorded_at: datetime
    kwh: float | None
    kvah: float | None
    voltage_r: float | None = Field(validation_alias="volt_r")

    @field_serializer("recorded_at")
    def serialize_timestamp(self, value: datetime) -> str:
        # The portal displays local Jaipur time. The database stores the same instant in UTC.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class SyncResult(BaseModel):
    meters_synced: int
    network_nodes_synced: int
    transformers_synced: int
    synced_at: datetime

    @field_serializer("synced_at")
    def serialize_synced_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
