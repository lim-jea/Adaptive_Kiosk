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
import json
import math
import random
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE / "source_synthetic2"


# ─── 32 메뉴 카탈로그 ─────────────────────────────────────────────────────────
# (menu_id, item_id, item_name, category, is_hot, is_ice, is_coffee, caffeine_mg, unit_price)
# 23~32: 2026-05-06 신규 추가 (요청자 요청).
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
    (23, "I031", "카페모카",          "latte",     1, 1, 1,  95, 6200),
    (24, "I032", "블루레몬 에이드",   "ade",       0, 1, 0,   0, 6000),
    (25, "I033", "초코 라떼",         "frappe",    0, 1, 0,   0, 6300),
    (26, "I034", "딸기 라떼",         "frappe",    0, 1, 0,   0, 6300),
    (27, "I035", "유자차",            "tea",       1, 1, 0,   0, 5400),
    (28, "I036", "자몽차",            "tea",       1, 1, 0,   0, 5500),
    (29, "I037", "레몬차",            "tea",       1, 1, 0,   0, 5400),
    (30, "I038", "얼그레이 티",       "tea",       1, 1, 0,  40, 5400),
    (31, "I039", "페퍼민트 티",       "tea",       1, 0, 0,   0, 5400),
    (32, "I040", "요거트 스무디",     "smoothie",  0, 1, 0,   0, 6500),
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
        24: -0.4, 25: -0.5, 26: -0.5, 32: -0.4,                # 신규 에이드/블렌디드/스무디↓
        23: -0.1,                                              # 카페모카 약하게↓
        27: -0.2, 28: -0.2, 29: -0.2, 31: -0.3,                # 차류 morning↓
    },
    "lunch": {  # 11-14
        3: +0.4, 5: +0.4, 8: +0.3, 18: +0.2, 19: +0.2,
        17: -0.2, 15: -0.3,
        23: +0.2, 24: +0.2,                                    # 카페모카·블루레몬 라이트한 점심
    },
    "afternoon": {  # 14-18
        12: +0.6, 13: +0.5, 20: +0.5, 21: +0.5, 22: +0.4,      # 디저트/스무디↑
        18: +0.4, 19: +0.4, 16: +0.4,                          # 에이드/아이스티↑
        2: -0.4, 1: -0.4, 9: -0.3,                             # 정통 커피↓
        23: +0.3, 24: +0.5, 25: +0.4, 26: +0.4, 32: +0.5,      # 신규 디저트/에이드/스무디↑ (초코·딸기 라떼는 +0.4로 완화 — 카트 추천 쏠림 방지)
        28: +0.3, 29: +0.3,                                    # 자몽차/레몬차 약하게↑
    },
    "evening": {  # 18-22
        15: +0.6, 16: +0.5, 17: +0.5,                          # 디카페인 티↑
        4: +0.2, 11: +0.2,                                      # 달콤 라떼 weak↑
        2: -0.4, 3: -0.4, 7: -0.5, 1: -0.5,                    # 카페인 강한 것 ↓
        23: +0.2, 25: +0.3,                                    # 카페모카·초코라떼 디저트성
        27: +0.4, 28: +0.4, 29: +0.4, 31: +0.5,                # 디카페인 차류 ↑↑
        30: +0.2,                                              # 얼그레이 약하게↑
    },
    "night": {  # 22+ (or <6) — 영업시간 분포에서 거의 발생 안 함
        15: +0.7, 16: +0.5, 17: +0.6, 18: +0.3, 19: +0.3,
        1: -0.8, 2: -0.6, 3: -0.6, 7: -0.7, 9: -0.6, 8: -0.5,
        27: +0.6, 28: +0.5, 29: +0.5, 31: +0.7,                # 디카페인 차류↑↑
        23: -0.5,                                              # 카페모카 카페인↓
    },
}


# ─── prior: (gender, age_group) × menu ────────────────────────────────────────
# **backend `utils/recommendation_utils.py` 와 동일한 라벨 사용**
#   gender    : F / M
#   age_group : 20~29 / 30~39 / 40~49 / 50+
# (v2 1차 한국어 라벨은 backend lookup 키와 mismatch 되어 추천 미동작 → 영어로 통일)
GENDER_AGE_ADJ: dict[tuple[str, str], dict[int, float]] = {
    ("F", "20~29"): {10: +0.5, 11: +0.5, 12: +0.4, 13: +0.4,
                     18: +0.4, 19: +0.4, 20: +0.5, 21: +0.4, 16: +0.3,
                     23: +0.4, 24: +0.5, 25: +0.4, 26: +0.4, 32: +0.5,  # 신규 달콤커피·에이드·블렌디드·요거트 (초코·딸기 라떼는 +0.4)
                     27: +0.2},                                          # 유자차 약하게
    ("F", "30~39"): {4: +0.4, 5: +0.4, 8: +0.3, 13: +0.3, 14: +0.4, 16: +0.3, 11: +0.2,
                     23: +0.3, 25: +0.3,                                 # 카페모카·초코라떼
                     27: +0.3, 28: +0.3, 30: +0.3, 31: +0.2},            # 차류
    ("F", "40~49"): {2: +0.4, 3: +0.3, 7: +0.3, 15: +0.4, 17: +0.4, 14: +0.2,
                     27: +0.4, 28: +0.3, 30: +0.3, 31: +0.3},            # 차류 강세
    ("F", "50+"):   {2: +0.5, 7: +0.3, 9: +0.4, 15: +0.5, 17: +0.4,
                     27: +0.5, 28: +0.3, 30: +0.4, 31: +0.4},            # 차류 매우 강세
    ("M", "20~29"): {3: +0.6, 7: +0.5, 8: +0.4, 11: +0.3, 12: +0.2, 21: +0.2,
                     23: +0.2, 25: +0.3, 32: +0.2},                      # 카페모카·초코라떼·요거트
    ("M", "30~39"): {2: +0.4, 3: +0.4, 4: +0.3, 7: +0.5, 9: +0.3, 8: +0.3,
                     23: +0.2},                                          # 카페모카
    ("M", "40~49"): {2: +0.6, 9: +0.5, 7: +0.4, 1: +0.4, 17: +0.2,
                     30: +0.2},                                          # 얼그레이
    ("M", "50+"):   {2: +0.6, 9: +0.6, 1: +0.5, 17: +0.3, 4: +0.2,
                     28: +0.2, 30: +0.2},                                # 자몽차·얼그레이
}


# ─── 인구 분포 (kiosk 카페 가정) ─────────────────────────────────────────────
GENDER_DIST = {"F": 0.58, "M": 0.42}
AGE_DIST = {"20~29": 0.34, "30~39": 0.30, "40~49": 0.20, "50+": 0.16}


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


# ─── 대시보드 분석 위젯이 의미 있는 분포를 보여주기 위한 prior ───────────────
# 이 보강 컬럼들은 추천 산식(_compute_profile_stats / _compute_co_purchase_stats) 에
# 들어가지 않는다 → 추천 결과 byte-level 동일 보장.

# Order.used_recommendation: 추천 사용률 (한 주문 단위)
USED_RECOMMENDATION_RATE = 0.15           # 15%

# OrderItem.from_recommendation: used_recommendation=True 인 주문 안 라인 중에서만 True
FROM_RECOMMENDATION_RATE_GIVEN_USED = 0.55  # 추천 사용 주문 안 라인의 55%가 추천 출처

# KioskSession.is_simple_mode: 50대 이상은 더 자주 사용
SIMPLE_MODE_RATE = {"20~29": 0.02, "30~39": 0.02, "40~49": 0.04, "50+": 0.12}

# KioskSession.help_triggered: 도움 호출 빈도
HELP_TRIGGERED_RATE = {"20~29": 0.01, "30~39": 0.01, "40~49": 0.03, "50+": 0.07}

# KioskSession.end_reason 분포
END_REASON_DIST = {"completed": 0.88, "abandoned": 0.07, "timeout": 0.03, "error": 0.02}

# Order.status 분포 (운영 가정)
ORDER_STATUS_DIST = {"completed": 0.95, "cancelled": 0.04, "refunded": 0.01}

# 옵션 카탈로그 prior (group_name + option_name 만 분석에 사용 → option_item_id 는 임의 정수 OK)
# seed_menu.py 의 카탈로그를 단순화. ID 는 분석에 안 쓰이므로 25 부터 임의 부여.
OPTION_CATALOG = {
    "사이즈": [(25, "Tall", 0), (26, "Grande", 500), (27, "Venti", 1000)],
    "온도":   [(29, "HOT", 0), (30, "ICE", 0)],
    "샷 추가": [(31, "샷 추가 (+1)", 500)],
    "시럽":   [(33, "바닐라 시럽", 500), (34, "헤이즐넛 시럽", 500), (35, "카라멜 시럽", 500)],
    "휘핑크림": [(37, "휘핑크림 추가", 500)],
    "당도":   [(39, "기본", 0), (40, "덜 달게", 0), (41, "더 달게", 0)],
}

# 메뉴별 사용 가능한 옵션 그룹 (간단화 — 실제 seed_menu 와 100% 매칭은 아니어도 분석 위젯 의미 있음)
MENU_OPTION_GROUPS: dict[int, list[str]] = {
    # 커피류: 사이즈, 온도, 샷, 시럽
    1: ["사이즈"], 2: ["사이즈","샷 추가"], 3: ["사이즈","샷 추가"],
    4: ["사이즈","샷 추가","시럽"], 5: ["사이즈","샷 추가","시럽"],
    6: ["사이즈","샷 추가"], 7: ["사이즈"], 8: ["사이즈","샷 추가","시럽"],
    9: ["사이즈"], 10: ["사이즈","샷 추가","시럽","휘핑크림"],
    11: ["사이즈","샷 추가","시럽"],
    # 디저트/스무디: 휘핑크림, 당도
    12: ["사이즈","휘핑크림","당도"], 13: ["사이즈","휘핑크림","당도"],
    14: ["사이즈","휘핑크림","당도"],
    # 티: 온도, 당도
    15: ["사이즈","온도","당도"], 16: ["사이즈","당도"],
    17: ["사이즈","당도"],
    # 에이드/스무디/주스: 사이즈, 당도
    18: ["사이즈","당도"], 19: ["사이즈","당도"], 20: ["사이즈","당도"],
    21: ["사이즈","당도"], 22: ["사이즈"],
    # 신규 메뉴
    23: ["사이즈","온도","샷 추가","시럽"],          # 카페모카 (달콤한커피)
    24: ["사이즈","당도"],                           # 블루레몬 에이드
    25: ["사이즈","휘핑크림","당도"],                # 초코 라떼 (블렌디드)
    26: ["사이즈","휘핑크림","당도"],                # 딸기 라떼 (블렌디드)
    27: ["사이즈","당도"],                           # 유자차
    28: ["사이즈","당도"],                           # 자몽차
    29: ["사이즈","당도"],                           # 레몬차
    30: ["사이즈","당도"],                           # 얼그레이 티
    31: ["사이즈","당도"],                           # 페퍼민트 티
    32: ["사이즈","당도"],                           # 요거트 스무디
}


def sample_options_for_menu(menu_id: int, rng: np.random.Generator) -> list[dict]:
    """메뉴에 어울리는 옵션 그룹에서 1~2개 선택해 selected_options_json 형태 dict list 반환."""
    groups = MENU_OPTION_GROUPS.get(menu_id, ["사이즈"])
    # 평균 1.5개 그룹에서 옵션 선택
    n_groups = min(len(groups), 1 + int(rng.poisson(0.7)))
    chosen_groups = rng.choice(groups, size=n_groups, replace=False) if len(groups) >= n_groups else groups
    selected: list[dict] = []
    for g in chosen_groups:
        items = OPTION_CATALOG.get(g, [])
        if not items:
            continue
        idx = int(rng.integers(0, len(items)))
        oid, oname, extra = items[idx]
        selected.append({
            "option_item_id": int(oid),
            "option_name": oname,
            "extra_price": int(extra),
            "group_name": g,
        })
    return selected


def _sample_from_dist(dist: dict[str, float], rng: np.random.Generator) -> str:
    keys = list(dist.keys())
    probs = np.array(list(dist.values()))
    probs = probs / probs.sum()
    return keys[rng.choice(len(keys), p=probs)]


def generate(n_sessions: int, seed: int, out_dir: Path, max_share: float):
    rng = np.random.default_rng(seed)
    py_rand = random.Random(seed)
    # 보강 컬럼 추첨 전용 RNG — 메뉴/주문 추첨 rng 의 state 를 절대 건드리지 않게 분리.
    # 같은 seed 라도 보강 추첨이 메뉴 분포에 영향 0 → 추천 결과 byte-level 동일 보장.
    enrich_rng = np.random.default_rng(seed + 9_999_991)

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

        # 인구별 prior 적용해서 is_simple_mode / help_triggered 분포 부여 (enrich_rng 사용 — 메뉴 rng 무영향)
        sm_rate = SIMPLE_MODE_RATE.get(age, 0.02)
        ht_rate = HELP_TRIGGERED_RATE.get(age, 0.01)
        is_simple_mode = int(enrich_rng.random() < sm_rate)
        help_triggered = int(enrich_rng.random() < ht_rate)
        end_reason = _sample_from_dist(END_REASON_DIST, enrich_rng)

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
            "is_simple_mode": is_simple_mode,
            "help_triggered": help_triggered,
            "end_reason": end_reason,
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

    rec_events_rows: list[dict] = []
    rec_event_id_seq = 0
    category_by_mid = {m[0]: m[3] for m in MENU_CATALOG}

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

        # 주문 단위 used_recommendation / order.status (enrich_rng 사용)
        used_recommendation = int(enrich_rng.random() < USED_RECOMMENDATION_RATE)
        order_status = _sample_from_dist(ORDER_STATUS_DIST, enrich_rng)

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

            # 라인별 from_recommendation: 추천 사용 주문에서만 일정 비율 True (enrich_rng)
            if used_recommendation and enrich_rng.random() < FROM_RECOMMENDATION_RATE_GIVEN_USED:
                from_rec = 1
            else:
                from_rec = 0

            # selected options (group_name + option_name 키 포함, enrich_rng)
            selected_opts = sample_options_for_menu(mid_int, enrich_rng)

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
                "from_recommendation": from_rec,
                "selected_options_json": json.dumps(selected_opts, ensure_ascii=False),
            })

        orders_rows.append({
            "order_id": order_id,
            "session_id": s["session_id"],
            "user_id": s["user_id"],
            "created_at": s["started_at"],
            "total_price": line_total,
            "item_count": n_items,
            "used_recommendation": used_recommendation,
            "is_promo": 0,
            "promo_discount_pct": 0.0,
            "status": order_status,
        })

        # RecommendationEvent 합성 — 주문이 추천을 사용했으면 1~2개 event 기록 (enrich_rng 만 사용)
        if used_recommendation:
            n_ev = 1 + int(enrich_rng.random() < 0.3)  # 70% 1개, 30% 2개
            for _ in range(n_ev):
                rec_event_id_seq += 1
                # 추천 type: situation(mode A) 70%, suggest(mode CF) 30%
                rec_type = "situation" if enrich_rng.random() < 0.7 else "suggest"
                # 추천한 메뉴: 그 컨텍스트의 인기 메뉴 중 하나 (enrich_rng 로 추첨)
                rec_mid = int(enrich_rng.choice(MENU_IDS, p=probs))
                # was_clicked, led_to_order
                was_clicked = int(enrich_rng.random() < 0.55)
                led_to_order = int(was_clicked and enrich_rng.random() < 0.6)
                rec_events_rows.append({
                    "id": rec_event_id_seq,
                    "session_id": s["session_id"],
                    "created_at": s["started_at"],
                    "preferred_category": category_by_mid.get(rec_mid, "coffee"),
                    "recommendation_type": rec_type,
                    "recommended_menu_id": rec_mid,
                    "was_clicked": was_clicked,
                    "led_to_order": led_to_order,
                })

    orders_df = pd.DataFrame(orders_rows)
    items_df = pd.DataFrame(items_rows)
    rec_events_df = pd.DataFrame(rec_events_rows)

    # 3. 검증
    print("\n=== 검증 ===")
    print(f"sessions: {len(sessions_df):,}")
    print(f"orders  : {len(orders_df):,}")
    print(f"items   : {len(items_df):,}")
    print(f"rec_events: {len(rec_events_df):,}")
    print(f"items/order = {len(items_df)/len(orders_df):.3f}")
    print()
    print(f"[대시보드 분포 점검]")
    print(f"  used_recommendation True 비율: {orders_df['used_recommendation'].mean()*100:.1f}%")
    print(f"  from_recommendation True 비율: {items_df['from_recommendation'].mean()*100:.1f}%")
    print(f"  is_simple_mode True 비율: {sessions_df['is_simple_mode'].mean()*100:.1f}%")
    print(f"  help_triggered True 비율: {sessions_df['help_triggered'].mean()*100:.1f}%")
    print(f"  end_reason 분포: {dict(sessions_df['end_reason'].value_counts(normalize=True).round(3))}")
    print(f"  order.status 분포: {dict(orders_df['status'].value_counts(normalize=True).round(3))}")
    if len(rec_events_df) > 0:
        print(f"  rec_events.was_clicked: {rec_events_df['was_clicked'].mean()*100:.1f}%")
        print(f"  rec_events.led_to_order: {rec_events_df['led_to_order'].mean()*100:.1f}%")

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
    rec_events_df.to_csv(out_dir / "recommendation_events.csv", index=False, encoding="utf-8")
    print(f"\n[saved] {out_dir}/  (kiosk_sessions, kiosk_orders, kiosk_order_items, recommendation_events).csv")

    return {
        "rows": {
            "sessions": len(sessions_df),
            "orders": len(orders_df),
            "items": len(items_df),
            "rec_events": len(rec_events_df),
        },
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
