"""조합형 TTS(audio_segments) 적용의 '객관적 타당성'을 확인하기 위한 캐시 커버리지 감사 스크립트.

목표:
- 조합형 템플릿(order_summary_simple/cart_total)과 fragments(static)에서 사용하는
  '정적 조각'이 디스크 캐시(data/tts_cache)에 얼마나 준비돼 있는지 수치로 보여준다.

주의:
- GENAI_TTS_ENABLED가 꺼져 있으면(기본) 새 WAV를 생성하지 못하므로,
  조합형의 체감 효과는 '캐시에 얼마나 미리 준비돼 있느냐'에 크게 좌우된다.

실행:
  backend/.venv/Scripts/python.exe backend/scripts/audit_tts_cache_coverage.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def main() -> int:
    _bootstrap_import_path()

    from services.canned_responses import get_cached_wav
    from services.canned_responses import load_scenarios

    parser = argparse.ArgumentParser(description="Audit tts_cache coverage for composition")
    parser.add_argument("--menus", type=int, default=0, help="DB에서 상위 N개 메뉴 이름도 타깃에 포함")
    parser.add_argument("--options", type=int, default=0, help="DB에서 상위 N개 옵션 이름도 타깃에 포함")
    args = parser.parse_args()

    load_scenarios()

    # 정적 조각 후보: fragments.static + 템플릿 parts 중 슬롯이 아닌 문자열
    import json

    data_path = Path(__file__).resolve().parents[1] / "data" / "canned_responses.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))

    static_frags = list((data.get("fragments") or {}).get("static") or [])
    templates = list(data.get("templates") or [])

    static_tpl_parts: list[str] = []
    for tpl in templates:
        parts = tpl.get("parts")
        if not parts:
            continue
        for p in parts:
            if isinstance(p, str) and p.startswith("{") and p.endswith("}"):
                continue
            static_tpl_parts.append(p)

    # 중복 제거 (순서 유지)
    def uniq(xs: list[str]) -> list[str]:
        out: list[str] = []
        seen = set()
        for x in xs:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    targets = uniq(static_frags + static_tpl_parts)

    # 선택: DB 메뉴/옵션 일부를 타깃에 포함 (조합형의 실제 성공률 추정에 도움)
    if args.menus or args.options:
        try:
            from core.database import get_session_factory
            from crud.menu import get_menus
            from sqlalchemy import select
            from models.menu import OptionItem

            factory = get_session_factory()
            if factory is not None:

                async def _fetch_from_db() -> list[str]:
                    out: list[str] = []
                    async with factory() as db:
                        if args.menus:
                            rows, _ = await get_menus(db, limit=max(0, int(args.menus)))
                            out.extend(r.get("name") for r in rows if r.get("name"))
                        if args.options:
                            q = select(OptionItem).limit(max(0, int(args.options)))
                            items = (await db.execute(q)).scalars().all()
                            out.extend(i.name for i in items if getattr(i, "name", None))
                    return out

                import asyncio

                extra = asyncio.run(_fetch_from_db())
                targets = uniq(targets + [x for x in extra if x])
        except Exception as e:
            print("DB targets skipped:", e)

    present: list[str] = []
    missing: list[str] = []
    for t in targets:
        wav = get_cached_wav(t)
        (present if wav is not None else missing).append(t)

    total = len(targets)
    hit = len(present)
    rate = (hit / total * 100.0) if total else 0.0

    print("== TTS cache coverage audit ==")
    print(f"targets={total} present={hit} missing={len(missing)} hit_rate={rate:.1f}%")

    print("\n[Present samples]")
    for s in present[:15]:
        print("-", repr(s))

    print("\n[Missing samples]")
    for s in missing[:25]:
        print("-", repr(s))

    print("\n== Interpretation ==")
    print("- hit_rate가 높을수록 audio_segments 조합이 실제로 성공할 확률이 높습니다.")
    print("- hit_rate가 낮으면 조합 경로는 자주 실패하고 response_text 기반 TTS/브라우저 폴백이 늘어납니다.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
