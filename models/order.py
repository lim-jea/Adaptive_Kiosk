import uuid

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from core.database import Base


def _generate_order_uuid():
    return uuid.uuid4().hex


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_uuid = Column(String(32), unique=True, nullable=False, default=_generate_order_uuid)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    total_price = Column(Integer, nullable=False)                         # 서버 최종 계산값
    used_recommendation = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="completed", nullable=False)

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Integer, nullable=False)       # 주문 시점 단가 스냅샷 (기본가 + 옵션 추가금)
    from_recommendation = Column(Boolean, default=False, nullable=False)

    order = relationship("Order", back_populates="items")
    options = relationship("OrderItemOption", back_populates="order_item")


class OrderItemOption(Base):
    """주문 시 선택한 옵션 스냅샷"""
    __tablename__ = "order_item_options"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    option_item_id = Column(Integer, ForeignKey("option_items.id"), nullable=False)
    option_name = Column(String(50), nullable=False)     # 주문 시점 스냅샷
    extra_price = Column(Integer, default=0, nullable=False)  # 주문 시점 스냅샷

    order_item = relationship("OrderItem", back_populates="options")
