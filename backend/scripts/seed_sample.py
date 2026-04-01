"""
테스트용 예시 데이터 생성 스크립트.
키오스크 등록 + 세션 + 주문 예시 데이터를 생성합니다.

이 파일은 개발/테스트 전용이며, 프로덕션 배포 전에 삭제하세요.
main.py에서 seed_sample_data()를 호출하여 사용합니다.
"""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.kiosk import Kiosk
from models.session import KioskSession
from models.order import Order, OrderItem, OrderItemOption
from models.menu import Menu, OptionItem
from crud.kiosk import register_kiosk

logger = logging.getLogger(__name__)


async def seed_sample_data(db: AsyncSession):
    """테스트용 예시 데이터를 삽입합니다. 이미 키오스크가 있으면 건너뜁니다."""
    kiosk_count = (await db.execute(select(func.count(Kiosk.id)))).scalar() or 0
    if kiosk_count > 0:
        logger.info("Sample data already exists. Skipping.")
        return

    # ─── 키오스크 3대 등록 ───
    kiosk1 = await register_kiosk(db, name="1층 로비 키오스크", location="서울 강남점 1층 입구")
    kiosk2 = await register_kiosk(db, name="2층 매장 키오스크", location="서울 강남점 2층 매장 내부")
    kiosk3 = await register_kiosk(db, name="3층 휴게실 키오스크", location="서울 강남점 3층 직원 휴게실")

    logger.info(f"Sample kiosks registered: {kiosk1.name} (api_key: {kiosk1.api_key[:16]}...)")
    logger.info(f"Sample kiosks registered: {kiosk2.name} (api_key: {kiosk2.api_key[:16]}...)")
    logger.info(f"Sample kiosks registered: {kiosk3.name} (api_key: {kiosk3.api_key[:16]}...)")

    # ─── 세션 3개 생성 (키오스크 1에서) ───
    session1 = KioskSession(kiosk_id=kiosk1.id)
    session2 = KioskSession(kiosk_id=kiosk1.id, is_simple_mode=True, estimated_age_group="60대", estimated_gender="female")
    session3 = KioskSession(kiosk_id=kiosk2.id)
    db.add_all([session1, session2, session3])
    await db.flush()

    # ─── 메뉴 ID 조회 ───
    americano = (await db.execute(select(Menu).where(Menu.name == "아이스 아메리카노"))).scalar_one_or_none()
    latte = (await db.execute(select(Menu).where(Menu.name == "따뜻한 카페라떼"))).scalar_one_or_none()
    smoothie = (await db.execute(select(Menu).where(Menu.name == "딸기 스무디"))).scalar_one_or_none()

    if not americano or not latte:
        logger.warning("Sample menus not found. Run seed_menu first.")
        await db.commit()
        return

    # 옵션 아이템 조회
    large_option = (await db.execute(select(OptionItem).where(OptionItem.name == "Large"))).scalar_one_or_none()

    # ─── 주문 1: 아이스 아메리카노 2잔 (Large) ───
    order1 = Order(session_id=session1.id, total_price=10000, used_recommendation=False)
    db.add(order1)
    await db.flush()

    order1_item = OrderItem(
        order_id=order1.id,
        menu_id=americano.id,
        quantity=2,
        unit_price=5000,  # 4500 + 500(Large)
        from_recommendation=False,
    )
    db.add(order1_item)
    await db.flush()

    if large_option:
        db.add(OrderItemOption(
            order_item_id=order1_item.id,
            option_item_id=large_option.id,
            option_name="Large",
            extra_price=500,
        ))

    # ─── 주문 2: 따뜻한 카페라떼 1잔 (Regular) ───
    order2 = Order(session_id=session2.id, total_price=5000, used_recommendation=True)
    db.add(order2)
    await db.flush()

    db.add(OrderItem(
        order_id=order2.id,
        menu_id=latte.id,
        quantity=1,
        unit_price=5000,
        from_recommendation=True,
    ))

    # ─── 주문 3: 딸기 스무디 1잔 ───
    if smoothie:
        order3 = Order(session_id=session3.id, total_price=5500, used_recommendation=False)
        db.add(order3)
        await db.flush()

        db.add(OrderItem(
            order_id=order3.id,
            menu_id=smoothie.id,
            quantity=1,
            unit_price=5500,
            from_recommendation=False,
        ))

    await db.commit()

    logger.info(
        "Sample data inserted: 3 kiosks, 3 sessions, 3 orders. "
        f"Use api_key '{kiosk1.api_key}' to test session creation."
    )
