"""
CSV-backed recommendation service.

The runtime recommendation flow is intentionally simple:

1. Profile recommendation:
   popularity within (gender, age_group, time_period)
2. Cart CF recommendation:
   co-purchase strength with menus already in cart
3. Final recommendation:
   profile score + cart CF score, with an optional light trend boost

This module keeps the public API surface compatible with the existing
endpoints while simplifying the internal scoring model. It also owns the
runtime CSV append path so recommendation data stays in one place.
"""

from __future__ import annotations

import csv
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model import KioskSession, Menu, Order
from services.trend_service import get_trend_service

logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_CSV_LOCK = threading.Lock()
_KNOWN_SESSION_UUIDS: set[str] | None = None
_KNOWN_ORDER_UUIDS: set[str] | None = None


class RecommendationEngine:
    RUNTIME_REFRESH_EVERY = 25

    def __init__(self):
        self.orders_df: Optional[pd.DataFrame] = None
        self.order_items_df: Optional[pd.DataFrame] = None
        self.sessions_df: Optional[pd.DataFrame] = None
        self.is_loaded = False

        self.menu_id_to_name: Dict[int, str] = {}
        self.valid_menu_ids: set[int] = set()

        self.hourly_weights: Dict[int, float] = {}
        self._profile_stats: Dict[str, Dict] = {}
        self._co_purchase_stats: Dict[str, Dict] = {}
        self._use_cache = False
        self._runtime_updates = 0

        self.load_data()

    # =========================================================================
    # CSV Loading / Cache Lifecycle
    # =========================================================================

    def load_data(self) -> bool:
        try:
            self.sessions_df = pd.read_csv(DATA_DIR / "kiosk_sessions.csv")
            self.orders_df = pd.read_csv(DATA_DIR / "orders.csv")
            self.order_items_df = pd.read_csv(DATA_DIR / "order_items.csv")

            self._normalize_frames()
            self._calculate_hourly_weights()
            self.is_loaded = True

            logger.info(
                "Recommendation CSV loaded: %s sessions, %s orders, %s items",
                len(self.sessions_df),
                len(self.orders_df),
                len(self.order_items_df),
            )
            return True
        except Exception as exc:
            logger.error("Failed to load recommendation data: %s", exc, exc_info=True)
            self.is_loaded = False
            return False

    def _normalize_frames(self) -> None:
        if self.sessions_df is not None:
            self.sessions_df = self.sessions_df.copy()
            self.sessions_df["session_id"] = range(1, len(self.sessions_df) + 1)

        if self.orders_df is not None:
            self.orders_df = self.orders_df.copy()
            self.orders_df["order_id"] = range(1, len(self.orders_df) + 1)
            self.orders_df["created_at"] = pd.to_datetime(
                self.orders_df["created_at"], errors="coerce"
            )

        if self.order_items_df is not None:
            self.order_items_df = self.order_items_df.copy()
            self.order_items_df["menu_id"] = pd.to_numeric(
                self.order_items_df["menu_id"], errors="coerce"
            )
            self.order_items_df["quantity"] = pd.to_numeric(
                self.order_items_df["quantity"], errors="coerce"
            ).fillna(0)
            self.order_items_df["unit_price"] = pd.to_numeric(
                self.order_items_df["unit_price"], errors="coerce"
            ).fillna(0)
            self.order_items_df["from_recommendation"] = (
                self.order_items_df["from_recommendation"]
                .astype(str)
                .str.lower()
                .isin({"true", "1", "yes"})
            )
            self.order_items_df = self.order_items_df.dropna(subset=["menu_id"])
            self.order_items_df["menu_id"] = self.order_items_df["menu_id"].astype(int)

    def _calculate_hourly_weights(self) -> None:
        if self.orders_df is None or self.orders_df.empty:
            self.hourly_weights = {h: 1.0 for h in range(24)}
            return

        orders_copy = self.orders_df.dropna(subset=["created_at"]).copy()
        if orders_copy.empty:
            self.hourly_weights = {h: 1.0 for h in range(24)}
            return

        orders_copy["hour"] = orders_copy["created_at"].dt.hour
        hourly_counts = orders_copy["hour"].value_counts()
        if hourly_counts.empty:
            self.hourly_weights = {h: 1.0 for h in range(24)}
            return

        max_count = hourly_counts.max()
        min_count = hourly_counts.min()
        range_count = max(max_count - min_count, 1)

        weights: Dict[int, float] = {}
        for hour in range(24):
            count = int(hourly_counts.get(hour, 0))
            if count == 0:
                weights[hour] = 0.5
                continue
            normalized = (count - min_count) / range_count
            weights[hour] = round(0.5 + normalized, 2)
        self.hourly_weights = weights

    def set_menu_mapping(self, menu_id_to_name: Dict[int, str]) -> None:
        self.menu_id_to_name = dict(menu_id_to_name)
        self.valid_menu_ids = set(menu_id_to_name.keys())
        logger.info("Recommendation menu mapping updated: %d menus", len(self.valid_menu_ids))

    def _hour_to_period(self, hour: int) -> str:
        if 6 <= hour < 11:
            return "morning"
        if 11 <= hour < 14:
            return "lunch"
        if 14 <= hour < 18:
            return "afternoon"
        if 18 <= hour < 22:
            return "evening"
        return "night"

    def _filter_valid_menu(self, menu_id: int) -> bool:
        return not self.valid_menu_ids or menu_id in self.valid_menu_ids

    # =========================================================================
    # Stats Computation
    # =========================================================================

    async def precompute_all_stats(self) -> tuple[Dict, Dict]:
        if not self.is_loaded:
            return {}, {}

        profile_stats = self._compute_profile_stats()
        co_purchase_stats = self._compute_co_purchase_stats()
        metadata = {
            "profile_keys": len(profile_stats),
            "co_purchase_menus": len(co_purchase_stats),
            "sessions_count": len(self.sessions_df) if self.sessions_df is not None else 0,
            "orders_count": len(self.orders_df) if self.orders_df is not None else 0,
            "items_count": len(self.order_items_df) if self.order_items_df is not None else 0,
        }
        return {"profile": profile_stats, "co_purchase": co_purchase_stats}, metadata

    def load_cached_stats(self, stats: Dict) -> bool:
        try:
            self._profile_stats = stats.get("profile", {}) or {}
            self._co_purchase_stats = stats.get("co_purchase", {}) or {}
            self._use_cache = bool(self._profile_stats or self._co_purchase_stats)
            self._runtime_updates = 0
            logger.info(
                "Recommendation cache loaded: profile=%d, co_purchase=%d",
                len(self._profile_stats),
                len(self._co_purchase_stats),
            )
            return True
        except Exception as exc:
            logger.error("Failed to load recommendation cache: %s", exc, exc_info=True)
            self._use_cache = False
            return False

    def refresh_runtime_cache(self) -> bool:
        if not self.load_data():
            return False
        stats = {
            "profile": self._compute_profile_stats(),
            "co_purchase": self._compute_co_purchase_stats(),
        }
        return self.load_cached_stats(stats)

    def note_runtime_update(self) -> bool:
        self._runtime_updates += 1
        if self._runtime_updates < self.RUNTIME_REFRESH_EVERY:
            return False
        logger.info(
            "Runtime recommendation refresh triggered after %d updates",
            self._runtime_updates,
        )
        refreshed = self.refresh_runtime_cache()
        if refreshed:
            self._runtime_updates = 0
        return refreshed

    # =========================================================================
    # Mapping / Normalization Helpers
    # =========================================================================

    def _profile_cache_key(self, gender: str, age_group: str, period: str) -> str:
        return f"gender:{gender},age:{age_group},period:{period}"

    def _co_purchase_cache_key(self, menu_id: int) -> str:
        return f"menu_id:{menu_id}"

    def _compute_profile_stats(self) -> Dict[str, Dict]:
        if (
            self.sessions_df is None
            or self.orders_df is None
            or self.order_items_df is None
            or self.sessions_df.empty
            or self.orders_df.empty
            or self.order_items_df.empty
        ):
            return {}

        sessions = self.sessions_df[["session_id", "estimated_gender", "estimated_age_group"]].copy()
        orders = self.orders_df.dropna(subset=["created_at"]).copy()
        orders["hour"] = orders["created_at"].dt.hour
        orders["period"] = orders["hour"].apply(self._hour_to_period)

        merged = orders.merge(sessions, on="session_id", how="inner")
        merged = merged.merge(self.order_items_df, on="order_id", how="inner")
        if self.valid_menu_ids:
            merged = merged[merged["menu_id"].isin(self.valid_menu_ids)]
        if merged.empty:
            return {}

        grouped = (
            merged.groupby(
                ["estimated_gender", "estimated_age_group", "period", "menu_id"],
                dropna=False,
            )["quantity"]
            .sum()
            .reset_index(name="count")
        )

        stats: Dict[str, Dict] = {}
        for (gender, age_group, period), group in grouped.groupby(
            ["estimated_gender", "estimated_age_group", "period"]
        ):
            total_count = int(group["count"].sum())
            recommendations = []
            for row in group.sort_values("count", ascending=False).itertuples(index=False):
                recommendations.append(
                    {
                        "menu_id": int(row.menu_id),
                        "count": int(row.count),
                        "popularity": round(float(row.count) / total_count, 4) if total_count else 0.0,
                    }
                )
            stats[self._profile_cache_key(str(gender), str(age_group), str(period))] = {
                "recommendations": recommendations[:10],
                "total_orders": int(
                    merged[
                        (merged["estimated_gender"] == gender)
                        & (merged["estimated_age_group"] == age_group)
                        & (merged["period"] == period)
                    ]["order_id"].nunique()
                ),
                "total_items": total_count,
            }
        return stats

    def _compute_co_purchase_stats(self) -> Dict[str, Dict]:
        if self.order_items_df is None or self.order_items_df.empty:
            return {}

        items = self.order_items_df.copy()
        if self.valid_menu_ids:
            items = items[items["menu_id"].isin(self.valid_menu_ids)]
        if items.empty:
            return {}

        pairs = items.merge(items, on="order_id", suffixes=("_x", "_y"))
        pairs = pairs[pairs["menu_id_x"] < pairs["menu_id_y"]]
        if pairs.empty:
            return {}

        counts = (
            pairs.groupby(["menu_id_x", "menu_id_y"])["order_id"]
            .count()
            .reset_index(name="count")
        )

        stats: Dict[str, Dict] = {}
        for menu_id in sorted(set(counts["menu_id_x"]).union(set(counts["menu_id_y"]))):
            menu_pairs = counts[
                (counts["menu_id_x"] == menu_id) | (counts["menu_id_y"] == menu_id)
            ]
            if menu_pairs.empty:
                continue

            total_count = int(menu_pairs["count"].sum())
            related: Dict[str, Dict] = {}
            for row in menu_pairs.itertuples(index=False):
                other_menu = int(row.menu_id_y if row.menu_id_x == menu_id else row.menu_id_x)
                pair_key = f"{min(int(row.menu_id_x), int(row.menu_id_y))}:{max(int(row.menu_id_x), int(row.menu_id_y))}"
                related[pair_key] = {
                    "count": int(row.count),
                    "strength": round(float(row.count) / total_count, 4) if total_count else 0.0,
                    "other_menu_id": other_menu,
                }
            stats[self._co_purchase_cache_key(int(menu_id))] = related
        return stats

    # =========================================================================
    # Score Helpers
    # =========================================================================

    def _get_profile_recommendations(self, gender: str, age_group: str, hour: int) -> Dict:
        period = self._hour_to_period(hour)
        cache_key = self._profile_cache_key(gender, age_group, period)
        return self._profile_stats.get(cache_key, {})

    def _get_global_popularity(self, menu_id: int) -> float:
        if not self._profile_stats:
            return 0.0
        values = []
        for payload in self._profile_stats.values():
            for rec in payload.get("recommendations", []):
                if int(rec["menu_id"]) == int(menu_id):
                    values.append(float(rec["popularity"]))
        return round(sum(values) / len(values), 4) if values else 0.0

    def _get_cart_cf_score(self, candidate_menu_id: int, cart_items: List[int]) -> float:
        if not cart_items:
            return 0.0
        strengths = []
        for selected_id in cart_items:
            cached_pairs = self._co_purchase_stats.get(self._co_purchase_cache_key(selected_id), {})
            for pair_stats in cached_pairs.values():
                if int(pair_stats.get("other_menu_id", -1)) == int(candidate_menu_id):
                    strengths.append(float(pair_stats.get("strength", 0.0)))
        if not strengths:
            return 0.0
        strongest = max(strengths)
        average = sum(strengths) / len(strengths)
        coverage_bonus = min(0.03, 0.01 * max(len(strengths) - 1, 0))
        return round((strongest * 0.75) + (average * 0.25) + coverage_bonus, 4)

    def _get_best_cart_evidence(
        self,
        candidate_menu_id: int,
        cart_items: List[int],
    ) -> Dict[str, float | int | str] | None:
        best: Dict[str, float | int | str] | None = None
        for selected_id in cart_items:
            cached_pairs = self._co_purchase_stats.get(self._co_purchase_cache_key(selected_id), {})
            for pair_stats in cached_pairs.values():
                if int(pair_stats.get("other_menu_id", -1)) != int(candidate_menu_id):
                    continue
                candidate = {
                    "source_menu_id": int(selected_id),
                    "source_menu_name": self.menu_id_to_name.get(int(selected_id), f"Menu_{selected_id}"),
                    "count": int(pair_stats.get("count", 0)),
                    "strength": float(pair_stats.get("strength", 0.0)),
                }
                if best is None or (
                    candidate["strength"] > best["strength"]
                    or (
                        candidate["strength"] == best["strength"]
                        and candidate["count"] > best["count"]
                    )
                ):
                    best = candidate
        return best

    def _build_trend_weight(
        self,
        menu_name: str,
        gender: str,
        age_group: str,
        hour: int,
        include_trend: bool,
    ) -> float:
        if not include_trend:
            return 1.0
        trend_service = get_trend_service()
        hour_weight = self.hourly_weights.get(hour, 1.0)
        return float(trend_service.get_weight(menu_name, gender, age_group, hour_weight))

    # =========================================================================
    # Recommendation APIs
    # =========================================================================

    def get_mode_a_recommendations(
        self,
        gender: str,
        age_group: str,
        hour: int,
        top_n: int = 5,
        include_trend: bool = True,
    ) -> Dict:
        if not self.is_loaded:
            return {"mode": "A", "error": "Engine not loaded"}

        period = self._hour_to_period(hour)
        profile_data = self._get_profile_recommendations(gender, age_group, hour)
        if not profile_data:
            return {
                "mode": "A",
                "situation": f"{gender}/{age_group}/{period}",
                "recommendations": [],
                "total_orders": 0,
                "total_items": 0,
                "cache_hit": self._use_cache,
            }

        recommendations = []
        for rank, rec in enumerate(profile_data.get("recommendations", [])[:top_n], 1):
            menu_id = int(rec["menu_id"])
            if not self._filter_valid_menu(menu_id):
                continue
            menu_name = self.menu_id_to_name.get(menu_id, f"Menu_{menu_id}")
            trend_weight = self._build_trend_weight(
                menu_name, gender, age_group, hour, include_trend
            )
            final_score = float(rec["popularity"]) * trend_weight
            recommendations.append(
                {
                    "rank": rank,
                    "menu_id": menu_id,
                    "menu_name": menu_name,
                    "count": int(rec["count"]),
                    "popularity": float(rec["popularity"]),
                    "trend_weight": round(trend_weight, 2),
                    "final_score": round(final_score, 4),
                    "reasoning": (
                        f"같은 성별/연령대/시간대 주문 {int(profile_data.get('total_orders', 0))}건에서 "
                        f"이 메뉴의 선택 비중이 약 {float(rec['popularity']) * 100:.1f}%예요."
                    ),
                }
            )

        recommendations.sort(key=lambda item: item["final_score"], reverse=True)
        for idx, item in enumerate(recommendations, 1):
            item["rank"] = idx

        return {
            "mode": "A",
            "situation": f"{gender}/{age_group}/{period}",
            "recommendations": recommendations[:top_n],
            "total_orders": int(profile_data.get("total_orders", 0)),
            "total_items": int(profile_data.get("total_items", 0)),
            "cache_hit": self._use_cache,
        }

    def get_integrated_recommendations(
        self,
        gender: str,
        age: int,
        cart_items: Optional[List[int]] = None,
        top_n: int = 5,
        include_trend: bool = True,
    ) -> Dict:
        from datetime import datetime
        from utils.recommendation_utils import age_to_age_group

        if not self.is_loaded:
            return {"mode": "CF", "error": "Engine not loaded"}

        cart_items = cart_items or []
        try:
            age_group = age_to_age_group(age)
        except ValueError as exc:
            return {"mode": "CF", "error": str(exc)}

        hour = datetime.now().hour
        period = self._hour_to_period(hour)
        profile_data = self._get_profile_recommendations(gender, age_group, hour)
        if not profile_data:
            return {"mode": "CF", "error": f"No data for profile: {gender}/{age_group}/{period}"}

        profile_map = {
            int(rec["menu_id"]): float(rec["popularity"])
            for rec in profile_data.get("recommendations", [])
            if self._filter_valid_menu(int(rec["menu_id"]))
        }
        candidate_menu_ids = set(profile_map.keys())
        for selected_id in cart_items:
            cached_pairs = self._co_purchase_stats.get(self._co_purchase_cache_key(selected_id), {})
            for pair_stats in cached_pairs.values():
                candidate_menu_ids.add(int(pair_stats.get("other_menu_id", -1)))
        candidate_menu_ids = {
            menu_id for menu_id in candidate_menu_ids
            if self._filter_valid_menu(menu_id) and menu_id not in cart_items
        }

        recommendations = []
        for menu_id in candidate_menu_ids:
            profile_popularity = profile_map.get(menu_id, 0.0)
            global_popularity = self._get_global_popularity(menu_id)
            profile_score = round((profile_popularity * 0.6) + (global_popularity * 0.4), 4)
            cart_cf_score = self._get_cart_cf_score(menu_id, cart_items)
            cf_score = round((profile_score * 0.4) + (cart_cf_score * 0.6), 4) if cart_items else profile_score

            menu_name = self.menu_id_to_name.get(menu_id, f"Menu_{menu_id}")
            trend_score = self._build_trend_weight(
                menu_name, gender, age_group, hour, include_trend
            )
            final_score = round(cf_score * trend_score, 4)
            cart_evidence = self._get_best_cart_evidence(menu_id, cart_items)

            if cart_evidence and float(cart_evidence["strength"]) > 0:
                reasoning = (
                    f"장바구니의 {cart_evidence['source_menu_name']}를 담은 다른 주문 중 "
                    f"약 {float(cart_evidence['strength']) * 100:.1f}%에서 함께 선택됐어요. "
                    f"({int(cart_evidence['count'])}건 근거)"
                )
            else:
                reasoning = (
                    f"같은 성별/연령대/시간대 주문 데이터에서 "
                    f"선택 비중이 약 {profile_popularity * 100:.1f}%인 메뉴예요."
                )

            recommendations.append(
                {
                    "rank": 0,
                    "menu_id": menu_id,
                    "menu_name": menu_name,
                    "cf_breakdown": {
                        "profile_popularity": round(profile_popularity, 4),
                        "global_popularity": round(global_popularity, 4),
                        "cart_cf_score": round(cart_cf_score, 4),
                        "cf_score": round(cf_score, 4),
                    },
                    "trend_score": round(trend_score, 2),
                    "final_score": final_score,
                    "reasoning": reasoning,
                }
            )

        recommendations.sort(key=lambda item: item["final_score"], reverse=True)
        recommendations = recommendations[:top_n]
        for idx, item in enumerate(recommendations, 1):
            item["rank"] = idx

        return {
            "mode": "CF",
            "user_context": {
                "gender": gender,
                "age_group": age_group,
                "period": period,
                "current_hour": hour,
            },
            "cart_items": [
                {
                    "menu_id": menu_id,
                    "menu_name": self.menu_id_to_name.get(menu_id, f"Menu_{menu_id}"),
                }
                for menu_id in cart_items
            ],
            "recommendations": recommendations,
            "cache_hit": self._use_cache,
        }


# ============================================================================
# Runtime CSV Append Helpers
# ============================================================================

def _read_existing_values(path: Path, key_field: str) -> set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return {row[key_field] for row in reader if row.get(key_field)}


def _ensure_csv_state() -> None:
    global _KNOWN_SESSION_UUIDS, _KNOWN_ORDER_UUIDS
    if _KNOWN_SESSION_UUIDS is None:
        _KNOWN_SESSION_UUIDS = _read_existing_values(DATA_DIR / "kiosk_sessions.csv", "session_uuid")
    if _KNOWN_ORDER_UUIDS is None:
        _KNOWN_ORDER_UUIDS = _read_existing_values(DATA_DIR / "orders.csv", "order_uuid")


def _append_row(path: Path, fieldnames: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def append_runtime_order_records(
    session: KioskSession,
    order: Order,
    items: list[dict],
) -> bool:
    """
    Append the completed runtime order and its session snapshot into CSV files.

    Returns True when at least one new row was appended.
    """
    _ensure_csv_state()
    appended = False

    session_row = {
        "session_uuid": session.session_uuid,
        "kiosk_id": session.kiosk_id,
        "started_at": session.started_at.isoformat() if session.started_at else "",
        "ended_at": session.ended_at.isoformat() if session.ended_at else "",
        "estimated_gender": session.estimated_gender or "",
        "estimated_age_group": session.estimated_age_group or "",
        "end_reason": session.end_reason or "",
        "is_simple_mode": int(bool(session.is_simple_mode)),
        "help_triggered": int(bool(session.help_triggered)),
        "status": session.status or "",
    }
    order_row = {
        "order_uuid": order.order_uuid,
        "session_id": session.id,
        "created_at": order.created_at.isoformat() if order.created_at else "",
        "total_price": order.total_price,
        "status": order.status,
        "used_recommendation": bool(order.used_recommendation),
    }

    with _CSV_LOCK:
        if session.session_uuid not in _KNOWN_SESSION_UUIDS:
            _append_row(
                DATA_DIR / "kiosk_sessions.csv",
                [
                    "session_uuid",
                    "kiosk_id",
                    "started_at",
                    "ended_at",
                    "estimated_gender",
                    "estimated_age_group",
                    "end_reason",
                    "is_simple_mode",
                    "help_triggered",
                    "status",
                ],
                session_row,
            )
            _KNOWN_SESSION_UUIDS.add(session.session_uuid)
            appended = True

        if order.order_uuid in _KNOWN_ORDER_UUIDS:
            return appended

        _append_row(
            DATA_DIR / "orders.csv",
            ["order_uuid", "session_id", "created_at", "total_price", "status", "used_recommendation"],
            order_row,
        )
        for item in items:
            _append_row(
                DATA_DIR / "order_items.csv",
                ["order_id", "menu_id", "quantity", "unit_price", "from_recommendation"],
                {
                    "order_id": order.id,
                    "menu_id": item["menu_id"],
                    "quantity": item["quantity"],
                    "unit_price": item["unit_price"],
                    "from_recommendation": bool(item["from_recommendation"]),
                },
            )
        _KNOWN_ORDER_UUIDS.add(order.order_uuid)
        appended = True

    return appended


# ============================================================================
# Singleton / Startup Initialization
# ============================================================================

_engine: Optional[RecommendationEngine] = None


def get_recommendation_engine() -> RecommendationEngine:
    global _engine
    if _engine is None:
        _engine = RecommendationEngine()
    return _engine


async def initialize_recommendation_engine(db: AsyncSession) -> bool:
    engine = get_recommendation_engine()
    if not engine.is_loaded:
        logger.warning("Recommendation engine not loaded")
        return False

    try:
        stmt = select(Menu).where(Menu.is_available == True)
        result = await db.execute(stmt)
        menus = result.scalars().all()
        menu_id_to_name = {m.id: m.name for m in menus}
        engine.set_menu_mapping(menu_id_to_name)
        logger.info("Recommendation menu mapping cached: %d menus", len(menu_id_to_name))
        return True
    except Exception as exc:
        logger.error("Failed to initialize menu mapping: %s", exc, exc_info=True)
        return False
