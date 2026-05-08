#testing
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


class Cart(Base):
    __tablename__ = "carts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), unique=True, nullable=False)
    status = Column(String(20), default="active", nullable=False)
    item_count = Column(Integer, default=0, nullable=False)
    total_quantity = Column(Integer, default=0, nullable=False)
    total_price = Column(Integer, default=0, nullable=False)
    contains_recommendation_item = Column(Boolean, default=False, nullable=False)
    cart_data = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


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
    menu_name_snapshot = Column(String(100), nullable=True)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Integer, nullable=False)
    line_total = Column(Integer, nullable=True)
    from_recommendation = Column(Boolean, default=False, nullable=False)
    selected_options_json = Column(JSON, nullable=True)

    order = relationship("Order", back_populates="items")


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


class SessionActivityLog(Base):
    __tablename__ = "session_activity_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    seq = Column(Integer, nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    event_type = Column(String(30), nullable=False)
    screen_name = Column(String(30), nullable=True)
    action_name = Column(String(50), nullable=False)
    target_type = Column(String(30), nullable=True)
    target_id = Column(String(100), nullable=True)
    target_label = Column(String(200), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    source = Column(String(20), nullable=False, default="ui")
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_activity_session_seq", "session_id", "seq"),
        Index("ix_activity_session_time", "session_id", "occurred_at"),
        Index("ix_activity_event_type", "event_type"),
    )


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


class SurveyResponse(Base):
    """설문 응답 단일 행. 한 키오스크 세션당 최대 1행 (session_id unique).
    status: partial(진행 중) / skipped(즉시 스킵) / completed(완료).

    저장 형식:
    - 객관식 23문항(q1~q23) 은 분석 편의를 위해 (value, label) 두 컬럼씩 명시.
    - 다중 선택 3종(f1/f2/g1) 과 인적 사항을 제외한 부가 옵션은 JSON 으로 보존.
    - 자유 텍스트 7개는 각자 컬럼.
    - survey_snapshot 에는 응답 당시 노출된 코드북 + 라벨 구성을 텍스트로 보존(추후 문항 변경 추적).
    """

    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), unique=True, nullable=False)
    status = Column(String(20), default="partial", nullable=False)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # 응답자 인적사항
    resp_age = Column(Integer, nullable=True)
    resp_gender = Column(String(20), nullable=True)
    resp_kiosk_freq = Column(String(20), nullable=True)

    # 객관식 23문항 — (value, label) 쌍으로 컬럼화
    q1_value = Column(Integer, nullable=True);  q1_label = Column(String(50), nullable=True)
    q2_value = Column(Integer, nullable=True);  q2_label = Column(String(50), nullable=True)
    q3_value = Column(Integer, nullable=True);  q3_label = Column(String(50), nullable=True)
    q4_value = Column(Integer, nullable=True);  q4_label = Column(String(50), nullable=True)
    q5_value = Column(Integer, nullable=True);  q5_label = Column(String(50), nullable=True)
    q6_value = Column(Integer, nullable=True);  q6_label = Column(String(50), nullable=True)
    q7_value = Column(Integer, nullable=True);  q7_label = Column(String(50), nullable=True)
    q8_value = Column(Integer, nullable=True);  q8_label = Column(String(50), nullable=True)
    q9_value = Column(Integer, nullable=True);  q9_label = Column(String(50), nullable=True)
    q10_value = Column(Integer, nullable=True); q10_label = Column(String(50), nullable=True)
    q11_value = Column(Integer, nullable=True); q11_label = Column(String(50), nullable=True)
    q12_value = Column(Integer, nullable=True); q12_label = Column(String(50), nullable=True)
    q13_value = Column(Integer, nullable=True); q13_label = Column(String(50), nullable=True)
    q14_value = Column(Integer, nullable=True); q14_label = Column(String(50), nullable=True)
    q15_value = Column(Integer, nullable=True); q15_label = Column(String(50), nullable=True)
    q16_value = Column(Integer, nullable=True); q16_label = Column(String(50), nullable=True)
    q17_value = Column(Integer, nullable=True); q17_label = Column(String(50), nullable=True)
    q18_value = Column(Integer, nullable=True); q18_label = Column(String(50), nullable=True)
    q19_value = Column(Integer, nullable=True); q19_label = Column(String(50), nullable=True)
    q20_value = Column(Integer, nullable=True); q20_label = Column(String(50), nullable=True)
    q21_value = Column(Integer, nullable=True); q21_label = Column(String(50), nullable=True)
    q22_value = Column(Integer, nullable=True); q22_label = Column(String(50), nullable=True)
    q23_value = Column(Integer, nullable=True); q23_label = Column(String(50), nullable=True)

    # q7 부가 플래그 (다른 키오스크 사용 경험 없음 체크 시 true)
    q7_no_experience = Column(Boolean, default=False, nullable=False)

    # 다중 선택 (옵션이 가변적이라 JSON 유지)
    multi_f1 = Column(JSON, nullable=False, default=list)
    multi_f2 = Column(JSON, nullable=False, default=list)
    multi_g1 = Column(JSON, nullable=False, default=list)

    # 자유 텍스트 7개
    text_b8_reason = Column(Text, nullable=True)
    text_d1_reason = Column(Text, nullable=True)
    text_e4 = Column(Text, nullable=True)
    text_f3 = Column(Text, nullable=True)
    text_h2 = Column(Text, nullable=True)
    text_i2 = Column(Text, nullable=True)
    text_i3 = Column(Text, nullable=True)

    # 응답 당시 노출된 설문 내용(코드북) 스냅샷 — 추후 문항이 바뀌어도 그 시점 답변 의미를 복원 가능
    survey_snapshot = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_survey_status", "status"),
        Index("ix_survey_session", "session_id"),
    )


__all__ = [
    "Kiosk",
    "KioskSession",
    "Cart",
    "Menu",
    "MenuOption",
    "Order",
    "OrderItem",
    "VisionEvent",
    "RecommendationEvent",
    "SessionActivityLog",
    "ChatMessage",
    "SurveyResponse",
]
