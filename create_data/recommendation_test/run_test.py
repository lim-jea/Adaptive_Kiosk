"""
격리된 환경에서 backend `recommendation_service.py` 를 두 데이터셋(legacy / 자체합성) 위에서
동일하게 실행해 결과를 비교한다.

사용:
  python run_test.py --dataset synth      # 자체 합성 데이터로 학습/추천
  python run_test.py --dataset legacy     # 기존 backend 데이터로 학습/추천
  python run_test.py --compare            # 둘 다 실행 후 통계 비교 리포트 출력

backend 코드를 import 하지 않고, 같은 폴더의 recommendation_service_copy.py 를 사용한다.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import types
from pathlib import Path

import pandas as pd


# ─── sqlalchemy stub ──────────────────────────────────────────────────────────
# backend recommendation_service_copy.py 가 모듈 최상단에서 import 하지만,
# 실제로 추천 로직(=우리가 테스트할 부분)은 sqlalchemy를 사용하지 않는다.
# sys.modules 에 빈 모듈을 미리 끼워 넣어 import 단계 통과시킴.
def _install_sqlalchemy_stub():
    if "sqlalchemy" in sys.modules:
        return
    mod = types.ModuleType("sqlalchemy")
    mod.select = lambda *a, **k: None
    sys.modules["sqlalchemy"] = mod

    ext_pkg = types.ModuleType("sqlalchemy.ext")
    sys.modules["sqlalchemy.ext"] = ext_pkg
    asyncio_mod = types.ModuleType("sqlalchemy.ext.asyncio")
    asyncio_mod.AsyncSession = type("AsyncSession", (), {})
    sys.modules["sqlalchemy.ext.asyncio"] = asyncio_mod


def _install_model_stub():
    """backend `model` 모듈 (KioskSession/Menu/Order) — 추천 로직과 무관."""
    if "model" in sys.modules:
        return
    mod = types.ModuleType("model")
    mod.KioskSession = type("KioskSession", (), {})
    mod.Menu = type("Menu", (), {})
    mod.Order = type("Order", (), {})
    sys.modules["model"] = mod


def _install_trend_stub():
    """backend `services.trend_service` — 우리 격리 검증에선 trend_weight 비활성."""
    if "services" not in sys.modules:
        sys.modules["services"] = types.ModuleType("services")
    if "services.trend_service" in sys.modules:
        return
    mod = types.ModuleType("services.trend_service")

    class _NoopTrend:
        def get_weight(self, *a, **k):
            return 1.0  # 곱셈 단위라 추천 점수에 영향 없음

    def get_trend_service():
        return _NoopTrend()

    mod.get_trend_service = get_trend_service
    sys.modules["services.trend_service"] = mod


_install_sqlalchemy_stub()
_install_model_stub()
_install_trend_stub()

HERE = Path(__file__).resolve().parent
LEGACY_DIR = HERE / "legacy_data"
SYNTH_DIR  = HERE / "data"
SYNTH2_DIR = HERE / "data2"
ENGINE_PATH = HERE / "recommendation_service_copy.py"

DATASET_DIRS = {
    "legacy": LEGACY_DIR,
    "synth":  SYNTH_DIR,
    "synth2": SYNTH2_DIR,
}


# 22 menu — backend seed_menu 기준
MENU_NAMES = [
    "에스프레소", "따뜻한 아메리카노", "아이스 아메리카노",
    "따뜻한 카페라떼", "아이스 카페라떼", "카푸치노",
    "콜드브루", "콜드브루 라떼", "드립 커피",
    "바닐라 라떼", "카라멜 마끼아또", "프라푸치노",
    "말차 프라페", "녹차 라떼", "캐모마일 티",
    "복숭아 아이스티", "자몽 허니 블랙 티", "레몬에이드",
    "자몽에이드", "딸기 스무디", "망고 스무디", "오렌지 주스",
]
MENU_ID_TO_NAME = {i + 1: name for i, name in enumerate(MENU_NAMES)}


def load_engine_module(data_dir: Path):
    """recommendation_service_copy.py 를 'DATA_DIR' 만 바꿔 import."""
    src = ENGINE_PATH.read_text(encoding="utf-8")
    # DATA_DIR 라인 패치 — backend 의 절대 경로를 우리 격리 폴더로 변경
    patched = []
    seen = False
    for line in src.splitlines():
        if not seen and line.strip().startswith("DATA_DIR"):
            patched.append(f'DATA_DIR = Path(r"{data_dir.as_posix()}")')
            seen = True
        else:
            patched.append(line)
    if not seen:
        # 일부 버전은 BASE / "data" 형태 — 안전망: 모듈 import 후 외부에서 덮어쓰기
        patched = src.splitlines()
    patched_src = "\n".join(patched)

    spec = importlib.util.spec_from_loader("recommendation_service_isolated", loader=None, origin=str(ENGINE_PATH))
    mod = importlib.util.module_from_spec(spec)
    mod.__file__ = str(ENGINE_PATH)
    exec(compile(patched_src, str(ENGINE_PATH), "exec"), mod.__dict__)
    # 이중 안전망 — DATA_DIR 모듈 변수 강제 설정
    mod.DATA_DIR = data_dir
    return mod


async def precompute_async(engine):
    """engine.precompute_all_stats 가 async 라 임시 이벤트루프로 실행."""
    import asyncio
    return await engine.precompute_all_stats()


def make_engine(data_dir: Path):
    mod = load_engine_module(data_dir)
    engine = mod.RecommendationEngine()
    engine.set_menu_mapping(MENU_ID_TO_NAME)
    # ★ profile_stats / co_purchase_stats 캐시를 채워야 추천이 동작한다.
    # backend는 부팅 시 precompute_all_stats() 비동기 호출 + load_cached_stats() 호출.
    # 격리 환경에선 동기적으로 같은 효과를 만든다.
    engine._profile_stats = engine._compute_profile_stats()
    engine._co_purchase_stats = engine._compute_co_purchase_stats()
    engine._use_cache = True
    return mod, engine


def summarize_engine(engine, label: str) -> dict:
    profile = engine._compute_profile_stats()
    co = engine._compute_co_purchase_stats()
    n_orders = len(engine.orders_df) if engine.orders_df is not None else 0
    n_sessions = len(engine.sessions_df) if engine.sessions_df is not None else 0
    n_items = len(engine.order_items_df) if engine.order_items_df is not None else 0

    # profile_stats: key = "gender:X,age:Y,period:Z" → 추천 후보 수
    profile_summary = {
        "n_keys": len(profile),
        "sample_keys": list(profile.keys())[:8],
        "avg_recs_per_key": round(
            sum(len(v.get("recommendations", [])) for v in profile.values()) / max(len(profile), 1), 2
        ),
        "avg_total_orders_per_key": round(
            sum(v.get("total_orders", 0) for v in profile.values()) / max(len(profile), 1), 1
        ),
    }
    co_summary = {
        "n_menus": len(co),
        "avg_pairs": round(
            sum(len(v) for v in co.values()) / max(len(co), 1), 2
        ),
    }

    summary = {
        "label": label,
        "rows": {"sessions": n_sessions, "orders": n_orders, "items": n_items},
        "profile_stats": profile_summary,
        "co_purchase_stats": co_summary,
    }
    return summary


def sample_recommendations(engine, label: str) -> dict:
    """샘플 사용자 컨텍스트로 mode_a 추천 호출.
    legacy/synth 라벨 포맷이 달라서, **논리적 컨텍스트**를 키로 두고
    각 엔진의 실제 라벨로 번역해 쿼리한다. 결과 report 가 같은 키로 정렬되도록.
    """
    sess_df = engine.sessions_df
    items_df = engine.order_items_df
    if sess_df is not None and not sess_df.empty:
        actual_genders = sorted(sess_df["estimated_gender"].dropna().unique().tolist())
        actual_ages    = sorted(sess_df["estimated_age_group"].dropna().unique().tolist())
        print(f"  [{label}] data 내 gender 라벨: {actual_genders}")
        print(f"  [{label}] data 내 age_group 라벨: {actual_ages}")
    if items_df is not None and not items_df.empty:
        menu_ids_in_data = sorted(items_df["menu_id"].dropna().astype(int).unique().tolist())
        print(f"  [{label}] data 내 menu_id 분포 (샘플): {menu_ids_in_data[:10]} ... 총 {len(menu_ids_in_data)}개")
        print(f"  [{label}] valid_menu_ids 설정값: {sorted(engine.valid_menu_ids)[:10]}... 총 {len(engine.valid_menu_ids)}개")

    has_legacy_labels = "F" in (sess_df["estimated_gender"].unique() if sess_df is not None else [])

    def to_gender(logical: str) -> str:
        if has_legacy_labels:
            return {"female": "F", "male": "M"}[logical]
        return {"female": "여", "male": "남"}[logical]

    def to_age(logical: str) -> str:
        # logical: "20s" / "30s" / "50s"
        if has_legacy_labels:
            return {"20s": "20~29", "30s": "30~39", "50s": "50+"}[logical]
        return {"20s": "20대", "30s": "30대", "50s": "50대"}[logical]

    # 논리적 컨텍스트 — legacy/synth 모두 동일 키로 결과 저장 → report 가 짝지어 비교 가능
    logical_samples = [
        {"key": "female/20s/9h",  "gender": "female", "age": "20s", "hour": 9},
        {"key": "female/30s/13h", "gender": "female", "age": "30s", "hour": 13},
        {"key": "male/30s/19h",   "gender": "male",   "age": "30s", "hour": 19},
        {"key": "male/50s/8h",    "gender": "male",   "age": "50s", "hour": 8},
    ]
    out = {}
    for s in logical_samples:
        gender = to_gender(s["gender"])
        age = to_age(s["age"])
        recs = engine.get_mode_a_recommendations(
            gender=gender, age_group=age, hour=s["hour"], top_n=5
        )
        recs_short = [
            {"menu_name": r.get("menu_name"), "menu_id": r.get("menu_id"),
             "popularity": round(r.get("popularity", 0), 4)}
            for r in recs.get("recommendations", [])
        ]
        if not recs_short:
            period = engine._hour_to_period(s["hour"])
            key = engine._profile_cache_key(gender, age, period)
            cached = engine._profile_stats.get(key, {})
            print(f"  [{label}] 빈 추천 — key={key!r} cached_recs={len(cached.get('recommendations', []))}")
        out[s["key"]] = recs_short
    return out


def run(data_dir: Path, label: str) -> dict:
    print(f"\n[{label}] data_dir = {data_dir}")
    if not (data_dir / "kiosk_sessions.csv").exists():
        raise SystemExit(f"{data_dir}/kiosk_sessions.csv 없음.")
    mod, engine = make_engine(data_dir)
    if not engine.is_loaded:
        raise SystemExit(f"[{label}] engine load 실패")

    summary = summarize_engine(engine, label)
    summary["sample_recommendations"] = sample_recommendations(engine, label)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def compare_multi(results: dict[str, dict]) -> str:
    """results: {label: summary_dict}. 임의 N개 데이터셋을 같은 컨텍스트 키로 비교."""
    labels = list(results.keys())
    lines = ["# 추천 엔진 비교 — 다중 데이터셋\n\n"]

    lines.append("## 데이터셋 요약\n\n")
    lines.append("| dataset | sessions | orders | items | items/order | profile_keys | avg_recs/key | co_purchase_menus | avg_pairs |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    for label in labels:
        s = results[label]
        rows = s["rows"]
        ipo = round(rows["items"] / max(rows["orders"], 1), 3)
        lines.append(f"| {label} | {rows['sessions']:,} | {rows['orders']:,} | {rows['items']:,} | {ipo} | "
                     f"{s['profile_stats']['n_keys']} | {s['profile_stats']['avg_recs_per_key']} | "
                     f"{s['co_purchase_stats']['n_menus']} | {s['co_purchase_stats']['avg_pairs']} |\n")

    lines.append("\n## 샘플 추천 비교\n")
    # 컨텍스트 키 합집합 (기본은 첫 데이터셋 기준 순서 유지)
    all_keys: list[str] = []
    seen = set()
    for label in labels:
        for k in results[label]["sample_recommendations"].keys():
            if k not in seen:
                seen.add(k)
                all_keys.append(k)

    for ctx in all_keys:
        lines.append(f"\n### context = {ctx}\n")
        for label in labels:
            recs = results[label]["sample_recommendations"].get(ctx, [])
            lines.append(f"\n**{label}**:\n")
            for r in recs:
                lines.append(f"- {r['menu_name']} (id={r['menu_id']}, pop={r['popularity']})\n")
    return "".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=list(DATASET_DIRS.keys()), default=None)
    ap.add_argument("--compare", action="store_true",
                    help="legacy + synth + synth2 (있는 데이터셋만) 비교 리포트")
    ap.add_argument("--compare-sets", nargs="+", default=None,
                    help="비교 대상 명시 (예: legacy synth2)")
    args = ap.parse_args()

    if args.compare or args.compare_sets:
        targets = args.compare_sets or ["legacy", "synth", "synth2"]
        results = {}
        for label in targets:
            d = DATASET_DIRS.get(label)
            if d is None or not (d / "kiosk_sessions.csv").exists():
                print(f"[skip] {label}: data dir 없음 ({d})")
                continue
            results[label] = run(d, label)
        if not results:
            raise SystemExit("비교 가능한 데이터셋이 없습니다.")
        report = compare_multi(results)
        out = HERE / "comparison_report.md"
        out.write_text(report, encoding="utf-8")
        (HERE / "comparison_report.json").write_text(
            json.dumps(results, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"\nsaved: {out}")
        return

    if args.dataset:
        run(DATASET_DIRS[args.dataset], args.dataset)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
