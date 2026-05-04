"""
합성 데이터 v2 생성기.

v1 (source_synthetic/) 의 문제점:
  - 단일 메뉴(말차 프라페)가 전체 9.84% 차지 — 22종 카페에서 비현실적
  - 40개 컨텍스트(성별×연령×시간대) 중 단 3개 메뉴만 top1 → 분리력 부족
  - items/order = 1.32 — co-purchase 학습 약함

v2 의 개선 목표:
  - 단일 메뉴의 global share ≤ 6%
  - 컨텍스트별 unique top1 메뉴 수 ≥ 15 / 40
  - items/order ≥ 1.6
  - period × 메뉴, 성별·연령 × 메뉴 prior 를 명시적으로 분리

산출:
  source_synthetic2/
    kiosk_sessions.csv
    kiosk_orders.csv
    kiosk_order_items.csv
  (sync_synthetic_data.py --source source_synthetic2 --target data2 로 변환)
"""
from __future__ import annotations

import argparse
import math
import random
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "source_synthetic2"


# ─── 22 메뉴 카탈로그 ─────────────────────────────────────────────────────────
# (menu_id, item_id, item_name, category, is_hot, is_ice, is_coffee, caffeine_mg, unit_price)
MENU_CATALOG = [
    (1,  "I001", "에스프레소",       "espresso",  1, 0, 1,  64, 3500),
    (2,  "I002", "따뜻한 아메리카노", "americano", 1, 0, 1, 150, 4000),
    (3,  "I003", "아이스 아메리카노", "americano", 0, 1, 1, 150, 4000),
    (4,  "I006", "따뜻한 카페라떼",   "latte",     1, 0, 1, 150, 4500),
    (5,  "I007", "아이스 카페라떼",   "latte",     0, 1, 1, 150, 4500),
    (6,  "I008", "카푸치노",          "cappuccino",1, 0, 1, 150, 4500),
    (7,  "I004", "콜드브루",          "coldbrew",  0, 1, 1, 200, 5000),
    (8,  "I011", "콜드브루 라떼",     "coldbrew",  0, 1, 1, 200, 5500),
    (9,  "I005", "드립 커피",         "drip",      1, 0, 1, 165, 4500),
    (10, "I009", "바닐라 라떼",       "latte",     0, 1, 1, 150, 5000),
    (11, "I010", "카라멜 마끼아또",   "latte",     0, 1, 1, 150, 5500),
    (12, "I012", "프라푸치노",        "frappe",    0, 1, 1, 100, 6000),
    (13, "I013", "말차 프라페",       "frappe",    0, 1, 0,  60, 6000),
    (14, "I015", "녹차 라떼",         "non-coffee",1, 0, 0,  60, 5000),
    (15, "I019", "캐모마일 티",       "tea",       1, 0, 0,   0, 4500),
    (16, "I026", "복숭아 아이스티",   "tea",       0, 1, 0,  20, 4500),
    (17, "I030", "자몽 허니 블랙 티", "tea",       1, 0, 0,  40, 5000),
    (18, "I027", "레몬에이드",        "ade",       0, 1, 0,   0, 5500),
    (19, "I028", "자몽에이드",        "ade",       0, 1, 0,   0, 5500),
    (20, "I024", "딸기 스무디",       "smoothie",  0, 1, 0,   0, 6500),
    (21, "I023", "망고 스무디",       "smoothie",  0, 1, 0,   0, 6500),
    (22, "I029", "오렌지 주스",       "juice",     0, 1, 0,   0, 5500),
]
N_MENU = len(MENU_CATALOG)
MENU_IDS = [m[0] for m in MENU_CATALOG]


# ─── prior: period × menu (additive logits, baseline=0) ───────────────────────
# **backend `recommendation_service._hour_to_period` 와 동일한 경계 사용**
#   morning  : 6-11
#   lunch    : 11-14
#   afternoon: 14-18
#   evening  : 18-22
#   night    : 22+ (or <6)
# 이 경계가 backend 와 어긋나면 generator 의 prior 가 backend 추천 키로 잘못 묶인다.
PERIOD_ADJ: dict[str, dict[int, float]] = {
    "morning": {  # 6-11
        2: +0.7, 3: +0.6, 7: +0.5, 9: +0.4, 1: +0.3,           # 정통 커피류↑
        12: -0.6, 13: -0.6, 20: -0.5, 21: -0.5, 22: -0.3,      # 디저트/스무디↓
        18: -0.3, 19: -0.3,                                     # 에이드↓
    },
    "lunch": {  # 11-14
        3: +0.4, 5: +0.4, 8: +0.3, 18: +0.2, 19: +0.2,
        17: -0.2, 15: -0.3,
    },
    "afternoon": {  # 14-18
        12: +0.6, 13: +0.5, 20: +0.5, 21: +0.5, 22: +0.4,      # 디저트/스무디↑
        18: +0.4, 19: +0.4, 16: +0.4,                          # 에이드/아이스티↑
        2: -0.4, 1: -0.4, 9: -0.3,                             # 정통 커피↓
    },
    "evening": {  # 18-22
        15: +0.6, 16: +0.5, 17: +0.5,                          # 디카페인 티↑
        4: +0.2, 11: +0.2,                                      # 달콤 라떼 weak↑
        2: -0.4, 3: -0.4, 7: -0.5, 1: -0.5,                    # 카페인 강한 것 ↓
    },
    "night": {  # 22+ (or <6) — 영업시간 분포에서 거의 발생 안 함
        15: +0.7, 16: +0.5, 17: +0.6, 18: +0.3, 19: +0.3,
        1: -0.8, 2: -0.6, 3: -0.6, 7: -0.7, 9: -0.6, 8: -0.5,
    },
}


# ─── prior: (gender, age_group) × menu ────────────────────────────────────────
GENDER_AGE_ADJ: dict[tuple[str, str], dict[int, float]] = {
    ("여", "20대"): {10: +0.5, 11: +0.5, 12: +0.4, 13: +0.4,
                    18: +0.4, 19: +0.4, 20: +0.5, 21: +0.4, 16: +0.3},
    ("여", "30대"): {4: +0.4, 5: +0.4, 8: +0.3, 13: +0.3, 14: +0.4, 16: +0.3, 11: +0.2},
    ("여", "40대"): {2: +0.4, 3: +0.3, 7: +0.3, 15: +0.4, 17: +0.4, 14: +0.2},
    ("여", "50대"): {2: +0.5, 7: +0.3, 9: +0.4, 15: +0.5, 17: +0.4},
    ("남", "20대"): {3: +0.6, 7: +0.5, 8: +0.4, 11: +0.3, 12: +0.2, 21: +0.2},
    ("남", "30대"): {2: +0.4, 3: +0.4, 4: +0.3, 7: +0.5, 9: +0.3, 8: +0.3},
    ("남", "40대"): {2: +0.6, 9: +0.5, 7: +0.4, 1: +0.4, 17: +0.2},
    ("남", "50대"): {2: +0.6, 9: +0.6, 1: +0.5, 17: +0.3, 4: +0.2},
}


# ─── 인구 분포 (kiosk 카페 가정) ─────────────────────────────────────────────
GENDER_DIST = {"여": 0.58, "남": 0.42}
AGE_DIST = {"20대": 0.34, "30대": 0.30, "40대": 0.20, "50대": 0.16}


# ─── 시간대 (backend recommendation_service._hour_to_period 와 동일) ─────────
def hour_to_period(h: int) -> str:
    if 6 <= h < 11:  return "morning"
    if 11 <= h < 14: return "lunch"
    if 14 <= h < 18: return "afternoon"
    if 18 <= h < 22: return "evening"
    return "night"


PERIODS = ["morning", "lunch", "afternoon", "evening", "night"]
# 영업 시간 분포 (시작 시각, 가중치)
HOUR_DIST = {
    7: 0.05, 8: 0.08, 9: 0.10,                            # morning
    11: 0.06, 12: 0.10, 13: 0.08,                         # lunch
    14: 0.08, 15: 0.10, 16: 0.09,                         # afternoon
    17: 0.07, 18: 0.06, 19: 0.05, 20: 0.04,               # dinner
    21: 0.02, 22: 0.02,                                   # late
}


# ─── 핵심: 컨텍스트별 메뉴 분포 ──────────────────────────────────────────────
def context_logits(gender: str, age: str, period: str, rng: np.random.Generator) -> np.ndarray:
    """22 메뉴에 대한 logit 벡터 (컨텍스트 의존)."""
    logits = np.zeros(N_MENU, dtype=float)
    for mid, adj in PERIOD_ADJ.get(period, {}).items():
        logits[mid - 1] += adj
    for mid, adj in GENDER_AGE_ADJ.get((gender, age), {}).items():
        logits[mid - 1] += adj
    # 컨텍스트별 노이즈 — 같은 컨텍스트라도 약간 변동 (Gumbel small)
    logits += rng.normal(0, 0.10, size=N_MENU)
    return logits


def softmax_capped(logits: np.ndarray, max_share: float = 0.06) -> np.ndarray:
    """softmax 후, 어떤 메뉴도 max_share 를 넘지 않도록 iterative cap.
    cap 초과분을 나머지에 비례 분배.
    """
    p = np.exp(logits - logits.max())
    p = p / p.sum()
    for _ in range(20):
        over = p > max_share
        if not over.any():
            break
        excess = (p[over] - max_share).sum()
        p[over] = max_share
        rest_idx = ~over
        if rest_idx.sum() == 0:
            break
        rest_total = p[rest_idx].sum()
        if rest_total <= 0:
            p[rest_idx] = excess / rest_idx.sum()
        else:
            p[rest_idx] += excess * (p[rest_idx] / rest_total)
    return p / p.sum()


def sample_session_count(target: int, rng: np.random.Generator) -> int:
    return target


def generate(n_sessions: int, seed: int, out_dir: Path, max_share: float):
    rng = np.random.default_rng(seed)
    py_rand = random.Random(seed)

    # 1. 세션 발생
    sessions = []
    genders = list(GENDER_DIST.keys())
    g_probs = np.array(list(GENDER_DIST.values()))
    ages = list(AGE_DIST.keys())
    a_probs = np.array(list(AGE_DIST.values()))
    hours = list(HOUR_DIST.keys())
    h_probs = np.array(list(HOUR_DIST.values()))
    h_probs = h_probs / h_probs.sum()

    base_date = pd.Timestamp("2025-01-01")
    for sid in range(1, n_sessions + 1):
        gender = genders[rng.choice(len(genders), p=g_probs)]
        age = ages[rng.choice(len(ages), p=a_probs)]
        hour = int(hours[rng.choice(len(hours), p=h_probs)])
        minute = int(rng.integers(0, 60))
        day_off = int(rng.integers(0, 365))
        started = base_date + pd.Timedelta(days=day_off, hours=hour, minutes=minute)
        ended = started + pd.Timedelta(minutes=int(rng.integers(2, 8)))

        sessions.append({
            "session_id": sid,
            "user_id": f"U{sid % 9999:04d}",
            "started_at": started.strftime("%Y-%m-%d %H:%M:%S"),
            "ended_at": ended.strftime("%Y-%m-%d %H:%M:%S"),
            "sex": gender,
            "age_10": age,
            "job": "office", "area": "seoul",
            "is_weekend": int(started.weekday() >= 5),
            "is_holiday": 0, "is_exam_period": 0, "is_promo": 0,
            "temp_c": int(rng.integers(0, 30)),
            "is_raining": 0, "is_snowing": 0, "pm25_ugm3": int(rng.integers(10, 80)),
        })

    sessions_df = pd.DataFrame(sessions)

    # 2. 주문 + 라인 생성
    catalog_by_mid = {m[0]: m for m in MENU_CATALOG}

    orders_rows = []
    items_rows = []
    order_id_seq = 0
    line_seq = 0

    # 컨텍스트별 분포를 캐시해서 동일 (gender,age,period) 안에선 같은 logit 사용
    # (실제 사람의 메뉴 선호가 시간대 안에서 안정적이라는 가정)
    ctx_logits_cache: dict[tuple[str, str, str], np.ndarray] = {}

    for s in sessions:
        gender, age = s["sex"], s["age_10"]
        h = int(s["started_at"][11:13])
        period = hour_to_period(h)

        key = (gender, age, period)
        if key not in ctx_logits_cache:
            ctx_logits_cache[key] = context_logits(gender, age, period, rng)
        probs = softmax_capped(ctx_logits_cache[key], max_share=max_share)

        # items/order: 1~3 (Poisson + 1, mean ~1.7)
        n_items = 1 + int(rng.poisson(0.7))
        n_items = min(n_items, 3)

        order_id_seq += 1
        order_id = order_id_seq

        # 한 주문 안에서는 동일 메뉴 중복 방지
        chosen_mids = rng.choice(MENU_IDS, size=n_items, replace=False, p=probs)
        line_total = 0
        for mid in chosen_mids:
            line_seq += 1
            mid_int = int(mid)
            mrow = catalog_by_mid[mid_int]
            qty = 1 if rng.random() > 0.05 else 2
            unit_price = int(mrow[8])
            line_total += unit_price * qty
            items_rows.append({
                "order_id": order_id,
                "item_id": mrow[1],
                "item_name": mrow[2],
                "category": mrow[3],
                "is_hot": mrow[4],
                "is_ice": mrow[5],
                "is_coffee": mrow[6],
                "caffeine_mg": mrow[7],
                "unit_price": unit_price,
                "quantity": qty,
            })

        orders_rows.append({
            "order_id": order_id,
            "session_id": s["session_id"],
            "user_id": s["user_id"],
            "created_at": s["started_at"],
            "total_price": line_total,
            "item_count": n_items,
            "used_recommendation": 0,
            "is_promo": 0,
            "promo_discount_pct": 0.0,
        })

    orders_df = pd.DataFrame(orders_rows)
    items_df = pd.DataFrame(items_rows)

    # 3. 검증
    print("\n=== 검증 ===")
    print(f"sessions: {len(sessions_df):,}")
    print(f"orders  : {len(orders_df):,}")
    print(f"items   : {len(items_df):,}")
    print(f"items/order = {len(items_df)/len(orders_df):.3f}")

    # global share
    share = items_df["item_id"].value_counts(normalize=True)
    name_by_iid = {m[1]: m[2] for m in MENU_CATALOG}
    print("\n[global menu share top 8]")
    for iid, p in share.head(8).items():
        print(f"  {iid} {name_by_iid[iid]:14s}: {p*100:5.2f}%")
    print(f"max share: {share.max()*100:.2f}% (target ≤ {max_share*100:.0f}%)")

    hhi = (share ** 2).sum()
    print(f"HHI: {hhi:.4f} (균등 0.0455, v1 0.0565, 목표 ≤ 0.06)")

    # context unique top1
    items_full = items_df.merge(orders_df[["order_id", "session_id"]], on="order_id").merge(
        sessions_df[["session_id", "sex", "age_10", "started_at"]], on="session_id"
    )
    items_full["hour"] = pd.to_datetime(items_full["started_at"]).dt.hour
    items_full["period"] = items_full["hour"].apply(hour_to_period)
    top1 = items_full.groupby(["sex", "age_10", "period"])["item_id"].apply(
        lambda s: s.value_counts().index[0]
    )
    n_unique = top1.nunique()
    print(f"\ncontext-level unique top1: {n_unique} / {len(top1)} (v1: 3/40, 목표 ≥ 15)")
    print("\ntop1 by gender×age×period:")
    print(top1.map(name_by_iid).value_counts().head(15))

    # 4. 저장
    out_dir.mkdir(parents=True, exist_ok=True)
    sessions_df.to_csv(out_dir / "kiosk_sessions.csv", index=False, encoding="utf-8")
    orders_df.to_csv(out_dir / "kiosk_orders.csv", index=False, encoding="utf-8")
    items_df.to_csv(out_dir / "kiosk_order_items.csv", index=False, encoding="utf-8")
    print(f"\n[saved] {out_dir}/  (kiosk_sessions, kiosk_orders, kiosk_order_items).csv")

    return {
        "rows": {"sessions": len(sessions_df), "orders": len(orders_df), "items": len(items_df)},
        "items_per_order": round(len(items_df) / len(orders_df), 3),
        "max_share_pct": round(share.max() * 100, 2),
        "hhi": round(hhi, 4),
        "unique_top1_per_context": int(n_unique),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-sessions", type=int, default=50000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--max-share", type=float, default=0.06,
                    help="단일 메뉴의 global share 상한 (0.06 = 6%)")
    args = ap.parse_args()
    generate(args.n_sessions, args.seed, args.out, args.max_share)


if __name__ == "__main__":
    main()
