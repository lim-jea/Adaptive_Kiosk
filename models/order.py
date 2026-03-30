from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("kiosk_sessions.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    total_time_seconds = Column(Integer, nullable=True)               # 주문 완료까지 소요 시간
    used_recommendation = Column(Boolean, default=False, nullable=False)
    status = Column(String(20), default="completed", nullable=False)  # completed / cancelled

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_id = Column(Integer, ForeignKey("menus.id"), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    from_recommendation = Column(Boolean, default=False, nullable=False)  # 추천 경유 여부

    order = relationship("Order", back_populates="items")
