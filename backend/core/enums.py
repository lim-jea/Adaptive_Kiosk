"""프로젝트 전역 enum 정의"""
from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"
    ABANDONED = "abandoned"


class SessionEndReason(str, Enum):
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class OrderStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ServingTemperature(str, Enum):
    HOT = "hot"
    COLD = "cold"
    BOTH = "both"
