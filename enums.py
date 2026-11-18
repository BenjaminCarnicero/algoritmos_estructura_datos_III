from enum import Enum

__all__ = ["TicketStatus", "ProductType"]


class TicketStatus(Enum):
    OPEN = "open"
    IN_PROGRESS = "in-progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class ProductType(Enum):
    KITCHEN = "kitchen"
    ELECTRONICS = "electronics"
    SMALL_APPLIANCES = "small_appliances"
