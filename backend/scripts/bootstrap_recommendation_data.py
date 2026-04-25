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
from math import ceil
from pathlib import Path

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from model import Kiosk, KioskSession, Order, OrderItem


logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _sample_markers(items: list[str]) -> list[str]:
    if not items:
        return []
    indexes = sorted({0, len(items) // 2, len(items) - 1})
    return [items[index] for index in indexes if items[index]]


def _read_csv_markers(path: Path, key_field: str) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = [row.get(key_field, "") for row in csv.DictReader(file)]
    return _sample_markers(rows)


async def _bootstrap_markers_already_present(
    db: AsyncSession,
    sessions_path: Path,
    orders_path: Path,
) -> bool:
    session_markers = _read_csv_markers(sessions_path, "session_uuid")
    order_markers = _read_csv_markers(orders_path, "order_uuid")
    if not session_markers or not order_markers:
        return False

    existing_sessions = set(
        (
            await db.execute(
                select(KioskSession.session_uuid).where(KioskSession.session_uuid.in_(session_markers))
            )
        ).scalars().all()
    )
    existing_orders = set(
        (
            await db.execute(
                select(Order.order_uuid).where(Order.order_uuid.in_(order_markers))
            )
        ).scalars().all()
    )
    return all(marker in existing_sessions for marker in session_markers) and all(
        marker in existing_orders for marker in order_markers
    )


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


def _chunk_rows(rows: list[dict], batch_size: int):
    for start in range(0, len(rows), batch_size):
        yield start, rows[start : start + batch_size]


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


async def _bulk_insert_sessions(
    db: AsyncSession,
    sessions_rows: list[dict],
    batch_size: int,
) -> int:
    total = len(sessions_rows)
    total_chunks = ceil(total / batch_size)

    for chunk_index, (start, chunk_rows) in enumerate(_chunk_rows(sessions_rows, batch_size), start=1):
        payload = []
        for offset, row in enumerate(chunk_rows, start=1):
            payload.append(
                {
                    "id": start + offset,
                    "session_uuid": row.get("session_uuid") or secrets.token_hex(16),
                    "kiosk_id": int(row.get("kiosk_id") or 1),
                    "started_at": _parse_datetime(row.get("started_at")),
                    "ended_at": _parse_datetime(row.get("ended_at")),
                    "end_reason": row.get("end_reason") or None,
                    "is_simple_mode": _is_truthy(row.get("is_simple_mode")),
                    "estimated_age_group": row.get("estimated_age_group") or None,
                    "estimated_gender": row.get("estimated_gender") or None,
                    "help_triggered": _is_truthy(row.get("help_triggered")),
                    "status": row.get("status") or "ended",
                }
            )

        await db.execute(insert(KioskSession), payload)
        await db.flush()
        logger.info(
            "Recommendation CSV bootstrap: imported sessions chunk %d/%d (%d/%d)",
            chunk_index,
            total_chunks,
            min(start + len(chunk_rows), total),
            total,
        )

    return total


async def _bulk_insert_orders(
    db: AsyncSession,
    order_rows: list[dict],
    batch_size: int,
) -> int:
    total = len(order_rows)
    total_chunks = ceil(total / batch_size)
    imported = 0

    for chunk_index, (start, chunk_rows) in enumerate(_chunk_rows(order_rows, batch_size), start=1):
        payload = []
        for offset, row in enumerate(chunk_rows, start=1):
            csv_session_id = int(row.get("session_id") or 0)
            if csv_session_id <= 0:
                continue
            payload.append(
                {
                    "id": start + offset,
                    "order_uuid": row.get("order_uuid") or secrets.token_hex(16),
                    "session_id": csv_session_id,
                    "created_at": _parse_datetime(row.get("created_at")),
                    "total_price": int(float(row.get("total_price") or 0)),
                    "used_recommendation": _is_truthy(row.get("used_recommendation")),
                    "status": row.get("status") or "completed",
                }
            )

        if not payload:
            continue

        await db.execute(insert(Order), payload)
        imported += len(payload)
        await db.flush()
        logger.info(
            "Recommendation CSV bootstrap: imported orders chunk %d/%d (%d/%d)",
            chunk_index,
            total_chunks,
            min(start + len(chunk_rows), total),
            total,
        )

    return imported


async def _bulk_insert_order_items(
    db: AsyncSession,
    item_rows: list[dict],
    batch_size: int,
) -> int:
    total = len(item_rows)
    total_chunks = ceil(total / batch_size)
    imported = 0

    for chunk_index, (start, chunk_rows) in enumerate(_chunk_rows(item_rows, batch_size), start=1):
        payload = []
        for row in chunk_rows:
            order_id = int(row.get("order_id") or 0)
            if order_id <= 0:
                continue
            quantity = int(float(row.get("quantity") or 0))
            unit_price = int(float(row.get("unit_price") or 0))
            payload.append(
                {
                    "order_id": order_id,
                    "menu_id": int(row.get("menu_id") or 0),
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": quantity * unit_price,
                    "from_recommendation": _is_truthy(row.get("from_recommendation")),
                    "selected_options_json": [],
                }
            )

        if not payload:
            continue

        await db.execute(insert(OrderItem), payload)
        imported += len(payload)
        await db.flush()
        logger.info(
            "Recommendation CSV bootstrap: imported order_items chunk %d/%d (%d/%d)",
            chunk_index,
            total_chunks,
            min(start + len(chunk_rows), total),
            total,
        )

    return imported


async def bootstrap_recommendation_csv_to_db(db: AsyncSession) -> bool:
    sessions_path = DATA_DIR / "kiosk_sessions.csv"
    orders_path = DATA_DIR / "orders.csv"
    items_path = DATA_DIR / "order_items.csv"
    if not sessions_path.exists() or not orders_path.exists() or not items_path.exists():
        logger.info("Recommendation CSV bootstrap skipped: source CSV files not found")
        return False

    if await _bootstrap_markers_already_present(db, sessions_path, orders_path):
        logger.info("Recommendation CSV bootstrap skipped: sample CSV markers already exist in DB")
        return False

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

    with sessions_path.open("r", encoding="utf-8-sig", newline="") as file:
        sessions_rows = list(csv.DictReader(file))
    with orders_path.open("r", encoding="utf-8-sig", newline="") as file:
        order_rows = list(csv.DictReader(file))
    with items_path.open("r", encoding="utf-8-sig", newline="") as file:
        item_rows = list(csv.DictReader(file))

    if not sessions_rows or not order_rows or not item_rows:
        logger.info("Recommendation CSV bootstrap skipped: source CSV files are empty")
        return False

    batch_size = max(100, int(settings.RECOMMENDATION_BOOTSTRAP_BATCH_SIZE or 2000))
    logger.info(
        "Recommendation CSV bootstrap started: sessions=%d, orders=%d, items=%d, batch_size=%d",
        len(sessions_rows),
        len(order_rows),
        len(item_rows),
        batch_size,
    )

    await _ensure_kiosks_from_csv(db, sessions_rows)
    imported_sessions = await _bulk_insert_sessions(db, sessions_rows, batch_size)
    imported_orders = await _bulk_insert_orders(db, order_rows, batch_size)
    imported_items = await _bulk_insert_order_items(db, item_rows, batch_size)

    await db.commit()
    logger.info(
        "Recommendation CSV bootstrap completed: imported %d sessions, %d orders, %d items into DB",
        imported_sessions,
        imported_orders,
        imported_items,
    )
    return True
