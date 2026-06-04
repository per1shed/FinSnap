from dataclasses import dataclass
from decimal import Decimal

from bot.constants import TransactionType


@dataclass
class DraftTransaction:
    amount: Decimal
    tx_type: TransactionType
    comment: str
    category: str
    bank_category: str = ""

    def to_state_dict(self) -> dict:
        return {
            "amount": str(self.amount),
            "tx_type": self.tx_type.value,
            "comment": self.comment,
            "category": self.category,
            "bank_category": self.bank_category,
        }

    @classmethod
    def from_state_dict(cls, data: dict) -> "DraftTransaction":
        return cls(
            amount=Decimal(data["amount"]),
            tx_type=TransactionType(data["tx_type"]),
            comment=data.get("comment", ""),
            category=data["category"],
            bank_category=data.get("bank_category", ""),
        )
