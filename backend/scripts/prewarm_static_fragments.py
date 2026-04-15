"""정적 조각(frags/static + 템플릿의 slot-less parts)만 제한적으로 프리워밍.

왜 필요한가?
- audio_segments 조합이 성공하려면 각 조각 문자열에 대응하는 WAV가 data/tts_cache에 있어야 한다.
- 현재 GENAI_TTS_ENABLED가 기본 OFF라 캐시 미스면 WAV를 새로 만들 수 없다.
- 이 스크립트는 '정적 조각'만 소량 생성해(대략 수십 개) 조합형의 실효성을 올린다.

실행(주의: GENAI_TTS_ENABLED=true + GENAI_API_KEY 필요):
  backend/.venv/Scripts/python.exe backend/scripts/prewarm_static_fragments.py

권장:
- include_menus/include_options(메뉴/옵션 조각 전체 생성)은 수가 커질 수 있으니 별도 전략으로.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


async def _amain(args) -> int:
    _bootstrap_import_path()

    from core.config import settings
    from services.chat_service import synthesize_speech

    if not getattr(settings, "GENAI_TTS_ENABLED", False):
        print("GENAI_TTS_ENABLED=false 입니다. .env에서 true로 켜고 실행하세요.")
        return 2

    import json

    data_path = Path(__file__).resolve().parents[1] / "data" / "canned_responses.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))

    static_frags = list((data.get("fragments") or {}).get("static") or [])
    templates = list(data.get("templates") or [])

    slotless_parts: list[str] = []
    for tpl in templates:
        parts = tpl.get("parts")
        if not parts:
            continue
        for p in parts:
            if isinstance(p, str) and p.startswith("{") and p.endswith("}"):
                continue
            slotless_parts.append(p)

    targets = []
    seen = set()
    for t in static_frags + slotless_parts:
        if not t or t in seen:
            continue
        seen.add(t)
        targets.append(t)

    # 선택: DB에서 메뉴/옵션 이름 조각 일부만 포함
    if args.menus or args.options:
        try:
            from core.database import get_session_factory
            from crud.menu import get_menus
            from sqlalchemy import select
            from models.menu import OptionItem

            factory = get_session_factory()
            if factory is not None:
                async with factory() as db:
                    menu_extra: list[str] = []
                    option_extra: list[str] = []
                    if args.menus:
                        rows, _ = await get_menus(db, limit=max(0, int(args.menus)))
                        menu_extra = [r.get("name") for r in rows if r.get("name")]
                    if args.options:
                        q = select(OptionItem).limit(max(0, int(args.options)))
                        items = (await db.execute(q)).scalars().all()
                        option_extra = [i.name for i in items if getattr(i, "name", None)]

                for name in menu_extra + option_extra:
                    if name and name not in seen:
                        seen.add(name)
                        targets.append(name)

        except Exception as e:
            print("DB fragments skipped:", e)

    if len(targets) > int(args.max_targets):
        print(f"targets={len(targets)} exceeds --max-targets={args.max_targets}. 줄이거나 --max-targets를 올리세요.")
        return 3

    print(f"targets={len(targets)}")

    n_ok = 0
    for t in targets:
        wav = None
        try:
            wav = await synthesize_speech(t)
        except Exception as e:
            print("FAIL", repr(t), e)
        if wav:
            n_ok += 1
            print("OK  ", repr(t))
        else:
            print("MISS", repr(t))

    print(f"done ok={n_ok}/{len(targets)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Prewarm static TTS fragments/templates into data/tts_cache")
    parser.add_argument("--menus", type=int, default=0, help="DB에서 상위 N개 메뉴 이름 조각도 포함")
    parser.add_argument("--options", type=int, default=0, help="DB에서 상위 N개 옵션 이름 조각도 포함")
    parser.add_argument("--max-targets", type=int, default=90, help="안전 상한(쿼터 보호). 초과 시 종료")
    args = parser.parse_args()
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    raise SystemExit(main())
