import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ParkingOperator:
    id: int
    name: str
    hourly_rate: int
    location_name: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    currency: str = "RWF"
    grace_period_minutes: int = 15
    api_base_url: Optional[str] = None
    api_key: Optional[str] = None
    integration_type: str = "api"
    is_active: bool = True
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "location_name": self.location_name,
            "address": self.address,
            "latitude": float(self.latitude) if self.latitude else None,
            "longitude": float(self.longitude) if self.longitude else None,
            "hourly_rate": self.hourly_rate,
            "currency": self.currency,
            "grace_period_minutes": self.grace_period_minutes,
            "integration_type": self.integration_type,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class ParkingSession:
    id: int
    plate_number: str
    entry_time: datetime
    hourly_rate_rwf: int
    operator_id: Optional[int] = None
    external_session_id: Optional[str] = None
    exit_time: Optional[datetime] = None
    status: str = "active"
    grace_period_end: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    # Joined fields from operator
    operator_name: Optional[str] = None
    operator_location: Optional[str] = None
    operator_address: Optional[str] = None

    @property
    def current_fee_rwf(self) -> int:
        """Calculate the current fee based on elapsed hours (ceiling-rounded)."""
        end = self.exit_time or datetime.now(timezone.utc)
        elapsed = end - self.entry_time
        elapsed_hours = elapsed.total_seconds() / 3600
        billable_hours = math.ceil(elapsed_hours)
        if billable_hours < 1:
            billable_hours = 1
        return billable_hours * self.hourly_rate_rwf

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "external_session_id": self.external_session_id,
            "operator_id": self.operator_id,
            "plate_number": self.plate_number,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "status": self.status,
            "hourly_rate_rwf": self.hourly_rate_rwf,
            "current_fee_rwf": self.current_fee_rwf,
            "grace_period_end": (
                self.grace_period_end.isoformat() if self.grace_period_end else None
            ),
            "last_synced_at": (
                self.last_synced_at.isoformat() if self.last_synced_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "operator_name": self.operator_name,
            "operator_location": self.operator_location,
            "operator_address": self.operator_address,
        }
