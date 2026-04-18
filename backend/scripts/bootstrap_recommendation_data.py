"""
Bootstrap recommendation CSV data into the runtime database.

This script-oriented module is intentionally kept under scripts/ so startup
data-loading logic stays grouped with other one-time initialization helpers.
"""

from __future__ import annotations

import csv
import logging
import secrets
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from model import Kiosk, KioskSession, Order, OrderItem


logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _is_truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


async def _ensure_kiosks_from_csv(db: AsyncSession, sessions_rows: list[dict]) -> None:
    kiosk_ids = sorted({int(row.get("kiosk_id") or 1) for row in sessions_rows})
    existing_ids = set((await db.execute(select(Kiosk.id))).scalars().all())

    for kiosk_id in kiosk_ids:
        if kiosk_id in existing_ids:
            continue
        kiosk = Kiosk(
            id=kiosk_id,
            name=f"Bootstrap Kiosk {kiosk_id}",
            location="Recommendation CSV Bootstrap",
            api_key=secrets.token_hex(32),
            is_active=True,
        )
        db.add(kiosk)

    await db.flush()


async def bootstrap_recommendation_csv_to_db(db: AsyncSession) -> bool:
    session_count = (await db.execute(select(func.count(KioskSession.id)))).scalar() or 0
    order_count = (await db.execute(select(func.count(Order.id)))).scalar() or 0
    item_count = (await db.execute(select(func.count(OrderItem.id)))).scalar() or 0

    if session_count or order_count or item_count:
        logger.info(
            "Recommendation CSV bootstrap skipped: existing DB data found "
            "(sessions=%d, orders=%d, items=%d)",
            session_count,
            order_count,
            item_count,
        )
        return False

    sessions_path = DATA_DIR / "kiosk_sessions.csv"
    orders_path = DATA_DIR / "orders.csv"
    items_path = DATA_DIR / "order_items.csv"
    if not sessions_path.exists() or not orders_path.exists() or not items_path.exists():
        logger.info("Recommendation CSV bootstrap skipped: source CSV files not found")
        return False

    with sessions_path.open("r", encoding="utf-8-sig", newline="") as file:
        sessions_rows = list(csv.DictReader(file))
    with orders_path.open("r", encoding="utf-8-sig", newline="") as file:
        order_rows = list(csv.DictReader(file))
    with items_path.open("r", encoding="utf-8-sig", newline="") as file:
        item_rows = list(csv.DictReader(file))

    if not sessions_rows or not order_rows or not item_rows:
        logger.info("Recommendation CSV bootstrap skipped: source CSV files are empty")
        return False

    await _ensure_kiosks_from_csv(db, sessions_rows)

    session_id_map: dict[int, int] = {}
    order_id_map: dict[int, int] = {}

    for csv_session_id, row in enumerate(sessions_rows, 1):
        session = KioskSession(
            session_uuid=row.get("session_uuid") or secrets.token_hex(16),
            kiosk_id=int(row.get("kiosk_id") or 1),
            started_at=_parse_datetime(row.get("started_at")),
            ended_at=_parse_datetime(row.get("ended_at")),
            end_reason=row.get("end_reason") or None,
            is_simple_mode=_is_truthy(row.get("is_simple_mode")),
            estimated_age_group=row.get("estimated_age_group") or None,
            estimated_gender=row.get("estimated_gender") or None,
            help_triggered=_is_truthy(row.get("help_triggered")),
            status=row.get("status") or "ended",
        )
        db.add(session)
        await db.flush()
        session_id_map[csv_session_id] = session.id

    for csv_order_id, row in enumerate(order_rows, 1):
        csv_session_id = int(row.get("session_id") or 0)
        mapped_session_id = session_id_map.get(csv_session_id)
        if not mapped_session_id:
            continue
        order = Order(
            order_uuid=row.get("order_uuid") or secrets.token_hex(16),
            session_id=mapped_session_id,
            created_at=_parse_datetime(row.get("created_at")),
            total_price=int(float(row.get("total_price") or 0)),
            used_recommendation=_is_truthy(row.get("used_recommendation")),
            status=row.get("status") or "completed",
        )
        db.add(order)
        await db.flush()
        order_id_map[csv_order_id] = order.id

    imported_items = 0
    for row in item_rows:
        csv_order_id = int(row.get("order_id") or 0)
        mapped_order_id = order_id_map.get(csv_order_id)
        if not mapped_order_id:
            continue
        quantity = int(float(row.get("quantity") or 0))
        unit_price = int(float(row.get("unit_price") or 0))
        item = OrderItem(
            order_id=mapped_order_id,
            menu_id=int(row.get("menu_id") or 0),
            quantity=quantity,
            unit_price=unit_price,
            line_total=quantity * unit_price,
            from_recommendation=_is_truthy(row.get("from_recommendation")),
            selected_options_json=[],
        )
        db.add(item)
        imported_items += 1

    await db.commit()
    logger.info(
        "Recommendation CSV bootstrap completed: imported %d sessions, %d orders, %d items into DB",
        len(session_id_map),
        len(order_id_map),
        imported_items,
    )
    return True
