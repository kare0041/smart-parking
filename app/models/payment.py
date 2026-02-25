from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Payment:
    id: int
    session_id: int
    amount_rwf: int
    phone_number: str
    payment_method: Optional[str] = None
    transaction_reference: Optional[str] = None
    momo_transaction_id: Optional[str] = None
    status: str = "pending"
    initiated_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "amount_rwf": self.amount_rwf,
            "payment_method": self.payment_method,
            "phone_number": self.phone_number,
            "transaction_reference": self.transaction_reference,
            "momo_transaction_id": self.momo_transaction_id,
            "status": self.status,
            "initiated_at": (
                self.initiated_at.isoformat() if self.initiated_at else None
            ),
            "confirmed_at": (
                self.confirmed_at.isoformat() if self.confirmed_at else None
            ),
        }
