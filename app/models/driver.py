from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Driver:
    id: int
    phone_number: str
    saved_plates: List[str] = field(default_factory=list)
    preferred_payment_method: Optional[str] = None
    push_subscription: Optional[dict] = None
    created_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "phone_number": self.phone_number,
            "saved_plates": self.saved_plates,
            "preferred_payment_method": self.preferred_payment_method,
            "push_subscription": self.push_subscription,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
