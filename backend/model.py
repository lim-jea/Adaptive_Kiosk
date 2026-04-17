import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from core.database import Base


# ============================================================================
# Kiosk / Session
# ============================================================================


def _generate_session_uuid():
    return uuid.uuid4().hex


class Kiosk(Base):
    __tablename__ = "kiosks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    location = Column(String(200), nullable=True)
    api_key = Column(String(64), unique=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    registered_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_seen_at = Column(DateTime, nullable=True)


class KioskSession(Base):
    __tablename__ = "kiosk_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_uuid = Column(String(32), unique=True, nullable=False, default=_generate_session_uuid)
    kiosk_id = Column(Integer, ForeignKey("kiosks.id"), nullable=False)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    ended_at = Column(DateTime, nullable=True)
    end_reason = Column(String(20), nullable=True)
    is_simple_mode = Column(Boolean, default=False, nullable=False)
    estimated_age_group = Column(String(20), nullable=True)
    estimated_gender = Column(String(10), nullable=True)
    help_triggered = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="active", nullable=False)
    voice_persona = Column(String(20), nullable=True)
    voice_current_stage = Column(String(30), nullable=True)
    voice_attempt_started_at = Column(DateTime, nullable=True)


# ============================================================================
# Menu / Order
# ============================================================================


class Menu(Base):
    __tablename__ = "menus"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(50), nullable=False)
    price = Column(Integer, nullable=False)
    icon_emoji = Column(String(10), nullable=True)
    calories = Column(Integer, nullable=True)
    serving_temperature = Column(String(10), nullable=True)
    is_caffeinated = Column(Boolean, default=False, nullable=False)
    description = Column(String(255), nullable=True)
    image_url = Column(String(500), nullable=True)
    is_available = Column(Boolean, default=True, nullable=False)

    options = relationship(
        "MenuOption",
        back_populates="menu",
        cascade="all, delete-orphan",
    )


class MenuOption(Base):
    __tablename__ = "menu_options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    group_name = Column(String(50), nullable=False)
    group_order = Column(Integer, default=0, nullable=False)
    option_name = Column(String(50), nullable=False)
    option_order = Column(Integer, default=0, nullable=False)
    extra_price = Column(Integer, default=0, nullable=False)
    is_required = Column(Boolean, default=True, nullable=False)
    min_select = Column(Integer, default=1, nullable=False)
    max_select = Column(Integer, default=1, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)

    menu = relationship("Menu", back_populates="options")


def _generate_order_uuid():
    return uuid.uuid4().hex


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_uuid = Column(String(32), unique=True, nullable=False, default=_generate_order_uuid)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    total_price = Column(Integer, nullable=False)
    used_recommendation = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="completed", nullable=False)

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Integer, nullable=False)
    from_recommendation = Column(Boolean, default=False, nullable=False)

    order = relationship("Order", back_populates="items")
    options = relationship("OrderItemOption", back_populates="order_item")


class OrderItemOption(Base):
    __tablename__ = "order_item_options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    option_item_id = Column(Integer, nullable=False)
    option_name = Column(String(50), nullable=False)
    extra_price = Column(Integer, default=0, nullable=False)

    order_item = relationship("OrderItem", back_populates="options")


# ============================================================================
# Events / Chat
# ============================================================================


class VisionEvent(Base):
    __tablename__ = "vision_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    low_light_corrected = Column(Boolean, default=False, nullable=False)
    detected_people_count = Column(Integer, default=0, nullable=False)
    masked_faces_count = Column(Integer, default=0, nullable=False)
    estimated_age_group = Column(String(20), nullable=True)
    estimated_gender = Column(String(10), nullable=True)
    age_confidence = Column(Float, nullable=True)
    confusion_detected = Column(Boolean, default=False, nullable=False)


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    preferred_category = Column(String(50), nullable=False)
    recommendation_type = Column(String(20), nullable=False)
    recommended_menu_id = Column(Integer, ForeignKey("menus.id"), nullable=True)
    was_clicked = Column(Boolean, default=False, nullable=False)
    led_to_order = Column(Boolean, default=False, nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    attempt_started_at = Column(DateTime, nullable=False)
    purpose = Column(String(30), nullable=False, default="voice_order")
    role = Column(String(10), nullable=False)
    content = Column(Text, nullable=False)
    intent = Column(String(30), nullable=True)
    matched_by = Column(String(20), nullable=True)
    response_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index(
            "ix_chat_session_attempt",
            "session_id",
            "attempt_started_at",
            "created_at",
        ),
    )


__all__ = [
    "Kiosk",
    "KioskSession",
    "Menu",
    "MenuOption",
    "Order",
    "OrderItem",
    "OrderItemOption",
    "VisionEvent",
    "RecommendationEvent",
    "ChatMessage",
]
