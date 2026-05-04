"""
합성 데이터(kiosk_sessions/orders/order_items) → backend recommendation_service 호환 스키마로 변환.

backend `services/recommendation_service.py` 의 `load_data()` 가 기대하는 컬럼:
- kiosk_sessions.csv : session_id, kiosk_id, started_at, estimated_gender, estimated_age_group, ...
- orders.csv         : order_id, session_id, created_at, total_price, used_recommendation, ...
- order_items.csv    : order_id, menu_id (int), quantity, unit_price, from_recommendation, ...

본 스크립트는 데이터를 변환만 한다. backend/data 에 직접 덮어쓰지 않고,
create_data/recommendation_test/data/ 안에 산출해 격리 환경에서 검증한 뒤 수동 복사.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE / "source_synthetic"     # 사용자가 Drive 산출물을 여기에 복사
DEFAULT_TARGET = HERE / "data"
DEFAULT_MAPPING = HERE / "menu_id_mapping.json"


# ─── 컬럼 매핑 ─────────────────────────────────────────────────────────────────

GENDER_MAP = {
    # 합성 데이터 표기 → backend 표기 (backend는 String(10)이므로 자유, 한국어 유지)
    "남": "남", "여": "여", "F": "여", "M": "남",
}


def load_menu_mapping(path: Path) -> tuple[dict[str, dict], list[dict]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    mapping = raw["mapping"]
    drops = []
    for item_id, spec in mapping.items():
        if spec.get("drop"):
            drops.append({"item_id": item_id, "reason": spec.get("reason", "")})
    return mapping, drops


def transform_sessions(src: pd.DataFrame) -> pd.DataFrame:
    """합성 sessions → backend kiosk_sessions.csv 스키마"""
    out = pd.DataFrame()
    out["session_id"] = src["session_id"]
    out["session_uuid"] = src["session_id"].apply(lambda x: f"sess_{int(x):08d}")
    out["kiosk_id"] = 1
    out["started_at"] = pd.to_datetime(src["started_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    out["ended_at"] = pd.to_datetime(src["ended_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    out["end_reason"] = "completed"
    out["is_simple_mode"] = 0
    out["estimated_age_group"] = src["age_10"].astype(str)
    out["estimated_gender"] = src["sex"].map(GENDER_MAP).fillna(src["sex"]).astype(str)
    out["help_triggered"] = 0
    out["status"] = "ended"
    return out


def transform_orders(src: pd.DataFrame) -> pd.DataFrame:
    """합성 orders → backend orders.csv 스키마"""
    out = pd.DataFrame()
    out["order_id"] = src["order_id"]
    out["order_uuid"] = src["order_id"].apply(lambda x: f"ord_{int(x):08d}")
    out["session_id"] = src["session_id"]
    out["created_at"] = pd.to_datetime(src["created_at"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    out["total_price"] = src["total_price"].astype(int)
    out["used_recommendation"] = src.get("used_recommendation", 0).astype(int)
    out["status"] = "completed"
    return out


def transform_order_items(src: pd.DataFrame, menu_mapping: dict[str, dict]) -> tuple[pd.DataFrame, dict[str, Any]]:
    """합성 order_items → backend order_items.csv 스키마.
    drop된 메뉴 (I014/I016/I017/I021/I022)는 제거.
    """
    rows = []
    drop_count = Counter()
    kept_menus = Counter()
    for r in src.itertuples(index=False):
        spec = menu_mapping.get(r.item_id)
        if spec is None:
            drop_count["unmapped"] += 1
            continue
        if spec.get("drop"):
            drop_count[r.item_id] += 1
            continue
        rows.append({
            "order_id": int(r.order_id),
            "menu_id": int(spec["menu_id"]),
            "menu_name_snapshot": spec["menu_name"],
            "quantity": int(getattr(r, "quantity", 1)),
            "unit_price": int(r.unit_price),
            "line_total": int(r.unit_price) * int(getattr(r, "quantity", 1)),
            "from_recommendation": False,
            "selected_options_json": "[]",
        })
        kept_menus[spec["menu_id"]] += 1
    df = pd.DataFrame(rows)
    stats = {
        "rows_in": int(len(src)),
        "rows_out": int(len(df)),
        "dropped_by_item": dict(drop_count),
        "kept_by_menu_id": dict(kept_menus),
    }
    return df, stats


def remove_empty_orders(orders: pd.DataFrame, items: pd.DataFrame) -> pd.DataFrame:
    """drop된 라인 때문에 텅 빈 주문이 생겼다면 제거 (cascade)."""
    valid_order_ids = set(items["order_id"].unique())
    keep = orders[orders["order_id"].isin(valid_order_ids)].copy()
    return keep


def remove_orphan_sessions(sessions: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    valid_session_ids = set(orders["session_id"].unique())
    keep = sessions[sessions["session_id"].isin(valid_session_ids)].copy()
    return keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE,
                    help="합성 CSV 폴더 (kiosk_sessions/orders/order_items)")
    ap.add_argument("--target", type=Path, default=DEFAULT_TARGET,
                    help="backend 호환 CSV 출력 폴더")
    ap.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING,
                    help="menu_id_mapping.json 경로")
    ap.add_argument("--dry-run", action="store_true", help="저장 없이 통계만 출력")
    args = ap.parse_args()

    src_dir = args.source
    if not src_dir.exists():
        raise SystemExit(
            f"source 폴더 없음: {src_dir}\n"
            f"Drive 의 'output/kiosk_*.csv' 3개를 {src_dir} 로 복사한 뒤 다시 실행하세요."
        )

    sessions_src = pd.read_csv(src_dir / "kiosk_sessions.csv")
    orders_src   = pd.read_csv(src_dir / "kiosk_orders.csv")
    items_src    = pd.read_csv(src_dir / "kiosk_order_items.csv")
    mapping, drops = load_menu_mapping(args.mapping)

    print(f"\n[input]")
    print(f"  sessions   : {len(sessions_src):,}")
    print(f"  orders     : {len(orders_src):,}")
    print(f"  order_items: {len(items_src):,}")
    print(f"  mapping drops: {len(drops)}")
    for d in drops:
        print(f"    - {d['item_id']}: {d['reason']}")

    sessions = transform_sessions(sessions_src)
    orders   = transform_orders(orders_src)
    items, item_stats = transform_order_items(items_src, mapping)

    # cascade: drop된 메뉴 → 빈 주문 → 고아 세션
    before_orders = len(orders)
    orders = remove_empty_orders(orders, items)
    sessions = remove_orphan_sessions(sessions, orders)

    print(f"\n[output]")
    print(f"  sessions   : {len(sessions):,}")
    print(f"  orders     : {len(orders):,}  (cascade 제거: {before_orders - len(orders):,})")
    print(f"  order_items: {len(items):,}  (drop {item_stats['rows_in'] - item_stats['rows_out']:,} 개 라인)")
    print(f"  drop by item_id: {item_stats['dropped_by_item']}")
    print(f"\n[메뉴별 라인 수 (top 10)]")
    top = sorted(item_stats["kept_by_menu_id"].items(), key=lambda x: -x[1])[:10]
    for mid, n in top:
        print(f"    menu_id={mid:2d}: {n:,}")

    if args.dry_run:
        print("\n[dry-run] 저장 안 함")
        return

    args.target.mkdir(parents=True, exist_ok=True)
    sessions.to_csv(args.target / "kiosk_sessions.csv", index=False, encoding="utf-8")
    orders.to_csv(args.target / "orders.csv", index=False, encoding="utf-8")
    items.to_csv(args.target / "order_items.csv", index=False, encoding="utf-8")
    print(f"\n[saved]")
    print(f"  {args.target / 'kiosk_sessions.csv'}")
    print(f"  {args.target / 'orders.csv'}")
    print(f"  {args.target / 'order_items.csv'}")


if __name__ == "__main__":
    main()
