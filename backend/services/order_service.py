"""주문 비즈니스 로직 - 가격 검증, 옵션 처리, 응답 구성"""
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model import Menu, Order, OrderItem
from crud.session import get_session_by_uuid, get_session_by_id
from crud import order as order_crud
from crud.cart import get_cart_by_session_id
from services.cart_service import calculate_unit_price, get_cart_items_for_checkout
from services.recommendation_service import append_runtime_order_records, get_recommendation_engine
from schemas import (
    OrderCreateRequest,
    OrderResponse,
    OrderItemResponse,
    OrderItemOptionResponse,
)
from schemas import make_error


# ─── 내부 응답 빌더 (이 파일 내부 전용) ─────────────────────────────────────
# get_order_response / list_order_responses 가 거의 동일한 응답을 만드므로,
# 빌드 형식 부분만 dedup. menu_name 결정 등 호출자 차이는 호출자가 책임.
def _build_order_item_response(item: OrderItem, *, menu_name: str) -> OrderItemResponse:
    option_snapshots = item.selected_options_json or []
    return OrderItemResponse(
        id=item.id,
        menu_name=menu_name,
        quantity=item.quantity,
        unit_price=item.unit_price,
        from_recommendation=item.from_recommendation,
        options=[
            OrderItemOptionResponse(
                option_name=opt["option_name"],
                extra_price=opt["extra_price"],
            )
            for opt in option_snapshots
        ],
    )


def _build_order_response(
    order: Order,
    *,
    session_uuid: str,
    items: list[OrderItemResponse],
) -> OrderResponse:
    return OrderResponse(
        order_uuid=order.order_uuid,
        session_uuid=session_uuid,
        created_at=order.created_at,
        total_price=order.total_price,
        used_recommendation=order.used_recommendation,
        status=order.status,
        items=items,
    )


async def create_order(db: AsyncSession, data: OrderCreateRequest) -> OrderResponse:
    session = await get_session_by_uuid(db, data.session_uuid)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=make_error(
                "SESSION_NOT_FOUND", "Invalid session_uuid", session_uuid=data.session_uuid
            ),
        )

    cart = None
    if data.items:
        source_items = [
            {
                "menu_name": item.menu_name,
                "quantity": item.quantity,
                "from_recommendation": item.from_recommendation,
                "selected_option_ids": [opt.option_item_id for opt in item.selected_options],
            }
            for item in data.items
        ]
        used_recommendation = (
            data.used_recommendation
            if data.used_recommendation is not None
            else any(item["from_recommendation"] for item in source_items)
        )
    else:
        cart, cart_items = await get_cart_items_for_checkout(db, session.id)
        source_items = [
            {
                "menu_name": item["menu_name"],
                "quantity": item["quantity"],
                "from_recommendation": item.get("from_recommendation", False),
                "selected_option_ids": [
                    option["option_item_id"] for option in item.get("options", [])
                ],
            }
            for item in cart_items
        ]
        used_recommendation = (
            data.used_recommendation
            if data.used_recommendation is not None
            else cart.contains_recommendation_item
        )

    order = await order_crud.insert_order(
        db,
        session_id=session.id,
        total_price=0,
        used_recommendation=used_recommendation,
    )

    response_items = []
    total_price = 0
    runtime_csv_items = []

    for item in source_items:
        option_ids = item["selected_option_ids"]
        # calculate_unit_price 가 검증된 옵션 객체 list 를 함께 반환하므로
        # 같은 옵션을 다시 fetch 하지 않는다.
        server_unit_price, menu, validated_options = await calculate_unit_price(
            db, item["menu_name"], option_ids
        )

        selected_options_json = [
            {
                "option_item_id": oi.id,
                "option_name": oi.option_name,
                "extra_price": oi.extra_price,
            }
            for oi in validated_options
        ]
        option_responses = [
            OrderItemOptionResponse(option_name=oi.option_name, extra_price=oi.extra_price)
            for oi in validated_options
        ]

        line_total = server_unit_price * item["quantity"]

        order_item = await order_crud.insert_order_item(
            db,
            order_id=order.id,
            menu_id=menu.id,
            menu_name_snapshot=menu.name,
            quantity=item["quantity"],
            unit_price=server_unit_price,
            line_total=line_total,
            from_recommendation=item["from_recommendation"],
            selected_options_json=selected_options_json,
        )

        total_price += line_total
        # runtime CSV (DB OrderItem mirror) — DB 컬럼 1:1 형식으로 누락 없이 기록
        runtime_csv_items.append(
            {
                "menu_id": menu.id,
                "menu_name_snapshot": menu.name,
                "quantity": item["quantity"],
                "unit_price": server_unit_price,
                "line_total": line_total,
                "from_recommendation": item["from_recommendation"],
                "selected_options_json": selected_options_json,
            }
        )

        response_items.append(
            OrderItemResponse(
                id=order_item.id,
                menu_name=menu.name,
                quantity=item["quantity"],
                unit_price=server_unit_price,
                from_recommendation=item["from_recommendation"],
                options=option_responses,
            )
        )

    # 할인 적용: discount_amount 만큼 차감하여 final_price 로 저장.
    # 결과적으로 orders.total_price 가 매출 분석에서 정확한 결제액으로 집계된다.
    # gross_total 자체는 ActivityLog payload (payment_start) 에 이미 기록됨.
    gross_total = total_price
    discount_amount = max(0, int(data.discount_amount or 0))
    if discount_amount > gross_total:
        discount_amount = gross_total
    final_price = gross_total - discount_amount

    order.total_price = final_price
    # 회귀 버그 수정: 프런트가 items 를 직접 전송하는 경우에도(cart=None) 서버 cart 를 마감 처리.
    # 그렇지 않으면 결제 후 재진입/새로고침 시 기존 장바구니가 살아 남는다.
    if cart is None:
        cart = await get_cart_by_session_id(db, session.id)
    if cart is not None:
        cart.status = "checked_out"
    await db.commit()
    await db.refresh(order)  # server_default 값 (created_at) 로드

    appended = append_runtime_order_records(session, order, runtime_csv_items)
    if appended:
        get_recommendation_engine().note_runtime_update()

    return OrderResponse(
        order_uuid=order.order_uuid,
        session_uuid=data.session_uuid,
        created_at=order.created_at,
        total_price=final_price,
        used_recommendation=order.used_recommendation,
        status=order.status,
        items=response_items,
    )


async def get_order_response(db: AsyncSession, order_uuid: str) -> OrderResponse | None:
    order = await order_crud.get_order_by_uuid(db, order_uuid)
    if not order:
        return None

    session = await get_session_by_id(db, order.session_id)
    session_uuid = session.session_uuid if session else ""

    # detail 응답: snapshot 비었을 때 Menu 추가 fetch 로 fallback
    response_items = []
    for item in order.items:
        if item.menu_name_snapshot:
            menu_name = item.menu_name_snapshot
        else:
            menu_result = await db.execute(select(Menu).where(Menu.id == item.menu_id))
            menu = menu_result.scalar_one_or_none()
            menu_name = menu.name if menu else ""
        response_items.append(_build_order_item_response(item, menu_name=menu_name))

    return _build_order_response(order, session_uuid=session_uuid, items=response_items)


async def list_order_responses(
    db: AsyncSession,
    *,
    status: str | None = None,
    kiosk_id: int | None = None,
    used_recommendation: bool | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[OrderResponse], int]:
    orders, total = await order_crud.list_orders(
        db,
        status=status,
        kiosk_id=kiosk_id,
        used_recommendation=used_recommendation,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
    )

    # list 응답: N+1 회피 위해 snapshot 없으면 빈 string (Menu 추가 fetch 안 함)
    responses = []
    for order in orders:
        session = await get_session_by_id(db, order.session_id)
        response_items = [
            _build_order_item_response(item, menu_name=item.menu_name_snapshot or "")
            for item in order.items
        ]
        responses.append(
            _build_order_response(
                order,
                session_uuid=session.session_uuid if session else "",
                items=response_items,
            )
        )
    return responses, total
