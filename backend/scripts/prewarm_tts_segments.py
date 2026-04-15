"""Prewarm TTS cache for audio segment composition.

목표:
- audio_segments로 이어붙여 재생할 '조각' 텍스트들을 미리 Gemini TTS로 합성해
  backend/data/tts_cache에 개별 WAV로 저장한다.

주의:
- Gemini TTS preview는 일일 호출 한도가 작다(코드 상 기본 비활성).
- 본 스크립트는 캐시 미스인 조각만 합성한다.

사용 예:
  # (권장) 아주 소량으로 먼저 테스트
  uv run python scripts/prewarm_tts_segments.py --limit 20

  # 메뉴/옵션까지 포함(조각 수 급증 가능)
  uv run python scripts/prewarm_tts_segments.py --include-db --limit 80
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import time

# 스크립트를 파일 경로로 직접 실행할 때(sys.path[0]=scripts/)도
# backend 패키지 루트(core/, services/, crud/ 등)를 import할 수 있게 한다.
_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from core.config import settings
from core.database import initialize_connection_pool, get_session_factory
from services.canned_responses import collect_prewarm_segments, get_cached_wav
from services.chat_service import synthesize_speech


async def _run(args) -> int:
    if not getattr(settings, "GENAI_TTS_ENABLED", False):
        print("GENAI_TTS_ENABLED=false 입니다. 조각을 라이브 합성하려면 .env에서 GENAI_TTS_ENABLED=true로 켜세요.")
        print("(캐시가 이미 채워져 있다면, 켜지 않아도 스킵/검사는 가능합니다.)")

    db = None
    if args.include_db:
        try:
            await initialize_connection_pool()
            factory = get_session_factory()
            if factory is None:
                raise RuntimeError("DB session factory not initialized")
            db = factory()
        except Exception as e:
            print(f"DB 연결 실패(메뉴/옵션 조각 제외하고 진행): {e}")
            db = None

    try:
        if db is not None:
            async with db as session:
                segments = await collect_prewarm_segments(session)
        else:
            segments = await collect_prewarm_segments(None)
    finally:
        pass

    segments = [s for s in segments if isinstance(s, str) and s.strip()]

    total = len(segments)
    if args.limit is not None:
        segments = segments[: max(0, int(args.limit))]

    print(f"segments_total={total} segments_target={len(segments)} include_db={bool(args.include_db)}")

    cached = 0
    generated = 0
    skipped = 0

    t0 = time.perf_counter()
    for i, text in enumerate(segments, start=1):
        if get_cached_wav(text) is not None:
            cached += 1
            continue

        if args.dry_run:
            skipped += 1
            continue

        wav = await synthesize_speech(text)
        if wav is None:
            # 라이브 합성 비활성이거나 실패
            skipped += 1
        else:
            generated += 1

        if i % 10 == 0 or i == len(segments):
            elapsed = (time.perf_counter() - t0) * 1000
            print(
                f"progress {i}/{len(segments)} cached={cached} generated={generated} skipped={skipped} ms={elapsed:.0f}",
                flush=True,
            )

    elapsed = (time.perf_counter() - t0) * 1000
    print(f"done cached={cached} generated={generated} skipped={skipped} ms={elapsed:.0f}")

    if not getattr(settings, "GENAI_API_KEY", "") and not args.dry_run:
        print("WARN: GENAI_API_KEY가 비어 있으면 라이브 합성이 불가능합니다.")

    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--include-db", action="store_true", help="DB에서 메뉴/옵션 이름 조각까지 수집")
    p.add_argument("--limit", type=int, default=None, help="최대 N개 조각만 처리(안전장치)")
    p.add_argument("--dry-run", action="store_true", help="합성은 하지 않고 대상/캐시 여부만 계산")
    args = p.parse_args(argv)

    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
