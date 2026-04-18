from __future__ import annotations

import argparse
import hashlib
import random
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd


# =============================================================================
# Paths / Constants
# =============================================================================

ROOT_DIR = Path(__file__).resolve().parent
RAW_DIR = ROOT_DIR / "raw"
INTERIM_DIR = ROOT_DIR / "interim"
OUTPUT_DIR = ROOT_DIR / "output"
BACKEND_DATA_DIR = ROOT_DIR.parent / "backend" / "data"

REQUIRED_RAW_COLUMNS = {
    "transaction_id",
    "transaction_date",
    "transaction_time",
    "transaction_qty",
    "product_id",
    "unit_price",
    "product_category",
    "product_type",
    "product_detail",
}

SUPPORTED_RAW_SUFFIXES = {".csv", ".xlsx", ".xls"}
ALLOWED_SOURCE_CATEGORIES = {"coffee", "tea", "drinking chocolate", "loose tea"}

AGE_GROUPS = (
    ("20~29", 0.28),
    ("30~39", 0.32),
    ("40~49", 0.22),
    ("50+", 0.18),
)

GENDERS = (
    ("M", 0.48),
    ("F", 0.52),
)


@dataclass(frozen=True)
class MenuCatalogItem:
    menu_id: int
    name: str
    category: str
    base_price: int
    keywords: tuple[str, ...]


MENU_CATALOG: tuple[MenuCatalogItem, ...] = (
    MenuCatalogItem(1, "에스프레소", "커피", 4000, ("espresso", "에스프레소")),
    MenuCatalogItem(2, "따뜻한 아메리카노", "커피", 4500, ("hot americano", "아메리카노", "americano")),
    MenuCatalogItem(3, "아이스 아메리카노", "커피", 4500, ("iced americano", "ice americano", "아이스 아메리카노")),
    MenuCatalogItem(4, "따뜻한 카페라떼", "커피", 5200, ("latte", "hot latte", "cafe latte", "카페라떼", "라떼")),
    MenuCatalogItem(5, "아이스 카페라떼", "커피", 5200, ("iced latte", "ice latte", "아이스 라떼")),
    MenuCatalogItem(6, "카푸치노", "커피", 5200, ("cappuccino", "카푸치노")),
    MenuCatalogItem(7, "콜드브루", "커피", 5200, ("cold brew", "콜드브루")),
    MenuCatalogItem(8, "콜드브루 라떼", "커피", 5800, ("cold brew latte", "콜드브루 라떼")),
    MenuCatalogItem(9, "드립 커피", "커피", 5000, ("drip coffee", "brewed coffee", "드립")),
    MenuCatalogItem(10, "바닐라 라떼", "달콤한커피", 5900, ("vanilla latte", "바닐라 라떼")),
    MenuCatalogItem(11, "카라멜 마끼아또", "달콤한커피", 6200, ("caramel macchiato", "카라멜 마끼아또")),
    MenuCatalogItem(12, "프라푸치노", "블렌디드", 6500, ("frappuccino", "프라푸치노", "blended coffee")),
    MenuCatalogItem(13, "말차 프라페", "블렌디드", 6300, ("matcha frappe", "말차 프라페", "green tea frappe")),
    MenuCatalogItem(14, "녹차 라떼", "티", 5800, ("matcha latte", "green tea latte", "녹차 라떼")),
    MenuCatalogItem(15, "캐모마일 티", "티", 4900, ("chamomile", "캐모마일")),
    MenuCatalogItem(16, "복숭아 아이스티", "달콤한티", 5200, ("peach iced tea", "복숭아 아이스티", "peach tea")),
    MenuCatalogItem(17, "자몽 허니 블랙 티", "달콤한티", 5700, ("grapefruit honey black tea", "자몽 허니 블랙 티")),
    MenuCatalogItem(18, "레몬에이드", "에이드", 6000, ("lemonade", "레몬에이드")),
    MenuCatalogItem(19, "자몽에이드", "에이드", 6200, ("grapefruit ade", "자몽에이드", "grapefruit ade")),
    MenuCatalogItem(20, "딸기 스무디", "스무디", 6500, ("strawberry smoothie", "딸기 스무디")),
    MenuCatalogItem(21, "망고 스무디", "스무디", 6500, ("mango smoothie", "망고 스무디")),
    MenuCatalogItem(22, "오렌지 주스", "주스", 5800, ("orange juice", "오렌지 주스")),
)


# =============================================================================
# Shared Helpers
# =============================================================================

def ensure_directories() -> None:
    for path in (RAW_DIR, INTERIM_DIR, OUTPUT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def normalize_text(value: str) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^0-9a-z가-힣\s]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _read_header(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, nrows=0)
    if suffix in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(path, nrows=0)
        except ImportError as exc:
            raise ImportError(
                f"Reading Excel file '{path.name}' requires openpyxl. "
                "Install openpyxl or save the file as CSV."
            ) from exc
    raise ValueError(f"Unsupported raw dataset format: {path.suffix}")


def discover_raw_dataset() -> Path:
    ensure_directories()
    candidates = sorted(
        path for path in RAW_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_RAW_SUFFIXES
    )
    for path in candidates:
        try:
            header = _read_header(path)
        except Exception:
            continue
        if REQUIRED_RAW_COLUMNS.issubset(set(header.columns)):
            return path
    raise FileNotFoundError(
        "No raw dataset with required columns found in create_data/raw. "
        f"Required columns: {sorted(REQUIRED_RAW_COLUMNS)}"
    )


def load_raw_dataset(path: Path | None = None) -> pd.DataFrame:
    raw_path = path or discover_raw_dataset()
    suffix = raw_path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(raw_path)
    elif suffix in {".xlsx", ".xls"}:
        try:
            df = pd.read_excel(raw_path)
        except ImportError as exc:
            raise ImportError(
                f"Reading Excel file '{raw_path.name}' requires openpyxl. "
                "Install openpyxl or save the file as CSV."
            ) from exc
    else:
        raise ValueError(f"Unsupported raw dataset format: {raw_path.suffix}")
    missing = REQUIRED_RAW_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    return df


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")


def weighted_pick(rng: random.Random, pairs: tuple[tuple[str, float], ...]) -> str:
    values = [pair[0] for pair in pairs]
    weights = [pair[1] for pair in pairs]
    return rng.choices(values, weights=weights, k=1)[0]


def make_order_uuid(transaction_id: str | int) -> str:
    base = hashlib.sha1(str(transaction_id).encode("utf-8")).hexdigest()[:24]
    return f"order_{base}"


def make_session_uuid(transaction_id: str | int) -> str:
    base = hashlib.sha1(f"session:{transaction_id}".encode("utf-8")).hexdigest()[:24]
    return f"session_{base}"


def unique_in_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


# =============================================================================
# Menu Mapping
# =============================================================================

def choose_menu_mapping(product_detail: str, product_type: str, product_category: str) -> MenuCatalogItem | None:
    detail_text = normalize_text(product_detail)
    type_text = normalize_text(product_type)
    category_text = normalize_text(product_category)
    if category_text not in ALLOWED_SOURCE_CATEGORIES:
        return None

    haystack = " ".join([detail_text, type_text, category_text]).strip()
    if not haystack:
        return None

    scored: list[tuple[int, int, MenuCatalogItem]] = []
    for item in MENU_CATALOG:
        score = 0
        longest = 0
        for keyword in item.keywords:
            normalized_keyword = normalize_text(keyword)
            if not normalized_keyword:
                continue
            keyword_len = len(normalized_keyword)
            if normalized_keyword == detail_text:
                score += 12
                longest = max(longest, keyword_len)
            elif normalized_keyword in detail_text:
                score += 8
                longest = max(longest, keyword_len)
            elif normalized_keyword == type_text:
                score += 7
                longest = max(longest, keyword_len)
            elif normalized_keyword in type_text:
                score += 5
                longest = max(longest, keyword_len)
            elif normalized_keyword == category_text:
                score += 3
                longest = max(longest, keyword_len)
            elif normalized_keyword in haystack:
                score += 1
                longest = max(longest, keyword_len)
        if score > 0:
            scored.append((score, longest, item))

    if not scored:
        return None

    scored.sort(key=lambda pair: (-pair[0], -pair[1], pair[2].menu_id))
    return scored[0][2]


def build_menu_mapping(raw_path: Path | None = None) -> Path:
    df = load_raw_dataset(raw_path)

    unique_products = (
        df[
            [
                "product_id",
                "product_category",
                "product_type",
                "product_detail",
                "unit_price",
            ]
        ]
        .drop_duplicates()
        .sort_values(["product_category", "product_type", "product_detail"])
    )

    rows = []
    for row in unique_products.itertuples(index=False):
        mapped = choose_menu_mapping(
            product_detail=row.product_detail,
            product_type=row.product_type,
            product_category=row.product_category,
        )
        rows.append(
            {
                "source_product_id": row.product_id,
                "source_product_category": row.product_category,
                "source_product_type": row.product_type,
                "source_product_detail": row.product_detail,
                "source_unit_price": row.unit_price,
                "normalized_menu_name": mapped.name if mapped else "",
                "normalized_category": mapped.category if mapped else "",
                "target_menu_id": mapped.menu_id if mapped else "",
                "target_menu_name": mapped.name if mapped else "",
                "target_base_price": mapped.base_price if mapped else "",
                "keep": bool(mapped),
                "review_required": not bool(mapped),
            }
        )

    out_df = pd.DataFrame(rows)
    out_path = INTERIM_DIR / "menu_mapping.csv"
    write_csv(out_df, out_path)
    return out_path


def load_mapping(mapping_path: Path | None = None) -> pd.DataFrame:
    path = mapping_path or (INTERIM_DIR / "menu_mapping.csv")
    if not path.exists():
        raise FileNotFoundError("menu_mapping.csv not found. Run build step first.")
    mapping = pd.read_csv(path)
    mapping = mapping[mapping["keep"] == True].copy()  # noqa: E712
    mapping["target_menu_id"] = pd.to_numeric(mapping["target_menu_id"], errors="coerce")
    mapping = mapping.dropna(subset=["target_menu_id"])
    mapping["target_menu_id"] = mapping["target_menu_id"].astype(int)
    return mapping


# =============================================================================
# Synthetic Session / Order / OrderItem Generation
# =============================================================================

def generate_synthetic_outputs(
    raw_path: Path | None = None,
    mapping_path: Path | None = None,
    publish_to_backend: bool = False,
    seed: int = 42,
) -> dict[str, Path]:
    ensure_directories()
    rng = random.Random(seed)

    raw_df = load_raw_dataset(raw_path)
    mapping_df = load_mapping(mapping_path)

    merged = raw_df.merge(
        mapping_df[
            [
                "source_product_id",
                "target_menu_id",
                "target_menu_name",
                "target_base_price",
            ]
        ],
        left_on="product_id",
        right_on="source_product_id",
        how="inner",
    ).copy()

    merged["created_at"] = pd.to_datetime(
        merged["transaction_date"].astype(str) + " " + merged["transaction_time"].astype(str),
        errors="coerce",
    )
    merged = merged.dropna(subset=["created_at"])
    merged["transaction_qty"] = pd.to_numeric(merged["transaction_qty"], errors="coerce").fillna(1).astype(int)
    merged["unit_price"] = pd.to_numeric(merged["unit_price"], errors="coerce").fillna(0).astype(int)
    merged["target_base_price"] = pd.to_numeric(
        merged["target_base_price"], errors="coerce"
    ).fillna(merged["unit_price"]).astype(int)
    merged = merged[merged["transaction_qty"] > 0].copy()

    order_groups = list(merged.groupby("transaction_id", sort=True))

    session_rows: list[dict] = []
    order_rows: list[dict] = []
    order_item_rows: list[dict] = []

    for order_index, (transaction_id, group) in enumerate(order_groups, start=1):
        group = group.sort_values("target_menu_id")
        created_at = group["created_at"].iloc[0].to_pydatetime()
        age_group = weighted_pick(rng, AGE_GROUPS)
        gender = weighted_pick(rng, GENDERS)
        used_recommendation = rng.random() < (0.18 if len(group) >= 2 else 0.12)
        simple_mode = 1 if (age_group == "50+" and rng.random() < 0.45) else 0
        help_triggered = 1 if (simple_mode and rng.random() < 0.35) else 0

        session_rows.append(
            {
                "session_uuid": make_session_uuid(transaction_id),
                "kiosk_id": 1,
                "started_at": (created_at - timedelta(minutes=rng.randint(2, 12))).isoformat(),
                "ended_at": (created_at + timedelta(minutes=rng.randint(4, 25))).isoformat(),
                "estimated_gender": gender,
                "estimated_age_group": age_group,
                "end_reason": "order_completed",
                "is_simple_mode": simple_mode,
                "help_triggered": help_triggered,
                "status": "ended",
            }
        )

        total_price = int((group["transaction_qty"] * group["target_base_price"]).sum())
        order_rows.append(
            {
                "order_uuid": make_order_uuid(transaction_id),
                "session_id": order_index,
                "created_at": created_at.isoformat(),
                "total_price": total_price,
                "status": "completed",
                "used_recommendation": bool(used_recommendation),
            }
        )

        recommended_item_index = rng.randrange(len(group)) if used_recommendation else None
        for item_index, item in enumerate(group.itertuples(index=False)):
            order_item_rows.append(
                {
                    "order_id": order_index,
                    "menu_id": int(item.target_menu_id),
                    "quantity": int(item.transaction_qty),
                    "unit_price": int(item.target_base_price),
                    "from_recommendation": bool(used_recommendation and item_index == recommended_item_index),
                }
            )

    sessions_df = pd.DataFrame(session_rows)
    orders_df = pd.DataFrame(order_rows)
    order_items_df = pd.DataFrame(order_item_rows)

    output_paths = {
        "sessions": OUTPUT_DIR / "kiosk_sessions.csv",
        "orders": OUTPUT_DIR / "orders.csv",
        "order_items": OUTPUT_DIR / "order_items.csv",
    }
    write_csv(sessions_df, output_paths["sessions"])
    write_csv(orders_df, output_paths["orders"])
    write_csv(order_items_df, output_paths["order_items"])

    if publish_to_backend:
        write_csv(sessions_df, BACKEND_DATA_DIR / "kiosk_sessions.csv")
        write_csv(orders_df, BACKEND_DATA_DIR / "orders.csv")
        write_csv(order_items_df, BACKEND_DATA_DIR / "order_items.csv")

    return output_paths


# =============================================================================
# Output Validation
# =============================================================================

def validate_outputs(output_dir: Path | None = None) -> list[str]:
    base = output_dir or OUTPUT_DIR
    sessions = pd.read_csv(base / "kiosk_sessions.csv")
    orders = pd.read_csv(base / "orders.csv")
    order_items = pd.read_csv(base / "order_items.csv")

    issues: list[str] = []

    if len(sessions) != len(orders):
        issues.append(f"sessions/orders count mismatch: {len(sessions)} vs {len(orders)}")

    missing_order_ids = set(order_items["order_id"]) - set(range(1, len(orders) + 1))
    if missing_order_ids:
        issues.append(f"order_items references unknown order ids: {sorted(list(missing_order_ids))[:10]}")

    order_totals = (
        order_items.assign(line_total=order_items["quantity"] * order_items["unit_price"])
        .groupby("order_id")["line_total"]
        .sum()
    )
    orders_indexed = orders.copy()
    orders_indexed["order_id"] = range(1, len(orders_indexed) + 1)
    merged = orders_indexed.merge(order_totals.rename("items_total"), on="order_id", how="left").fillna({"items_total": 0})
    mismatched = merged[merged["total_price"] != merged["items_total"]]
    if not mismatched.empty:
        issues.append(f"total_price mismatch rows: {len(mismatched)}")

    invalid_reco = orders[orders["used_recommendation"].astype(str).str.lower() == "true"]
    if not invalid_reco.empty:
        item_reco = (
            order_items.assign(
                from_recommendation=order_items["from_recommendation"].astype(str).str.lower() == "true"
            )
            .groupby("order_id")["from_recommendation"]
            .sum()
        )
        for idx in invalid_reco.index:
            order_id = idx + 1
            if item_reco.get(order_id, 0) < 1:
                issues.append(f"order {order_id} used_recommendation=true but no order item is flagged")
                break

    return issues


# =============================================================================
# Orchestration / CLI
# =============================================================================

def run_pipeline(
    raw_path: Path | None = None,
    mapping_path: Path | None = None,
    publish_to_backend: bool = False,
    seed: int = 42,
) -> dict[str, Path]:
    mapping_out = build_menu_mapping(raw_path)
    output_paths = generate_synthetic_outputs(
        raw_path=raw_path,
        mapping_path=mapping_path or mapping_out,
        publish_to_backend=publish_to_backend,
        seed=seed,
    )
    issues = validate_outputs()
    if issues:
        raise ValueError("Validation failed:\n" + "\n".join(f"- {issue}" for issue in issues))
    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build menu mapping, synthetic recommendation CSVs, and validate outputs."
    )
    parser.add_argument("--raw", type=Path, default=None, help="Optional raw CSV/XLSX path")
    parser.add_argument("--mapping", type=Path, default=None, help="Optional existing menu_mapping.csv path")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--publish-to-backend", action="store_true")
    parser.add_argument("--mapping-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    ensure_directories()

    if args.validate_only:
        issues = validate_outputs()
        if issues:
            print("VALIDATION_FAILED")
            for issue in issues:
                print(f"- {issue}")
            raise SystemExit(1)
        print("VALIDATION_OK")
        return

    mapping_path = build_menu_mapping(args.raw)
    print(f"menu mapping saved: {mapping_path}")

    if args.mapping_only:
        return

    outputs = generate_synthetic_outputs(
        raw_path=args.raw,
        mapping_path=args.mapping or mapping_path,
        publish_to_backend=args.publish_to_backend,
        seed=args.seed,
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")

    issues = validate_outputs()
    if issues:
        print("VALIDATION_FAILED")
        for issue in issues:
            print(f"- {issue}")
        raise SystemExit(1)

    print("VALIDATION_OK")


if __name__ == "__main__":
    main()
