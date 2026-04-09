"""
TTS 프리워밍 스크립트 (오프라인 일괄 합성 도구).

사용법:
    python -m scripts.prewarm_tts          # 누락된 음성만 합성
    python -m scripts.prewarm_tts --force  # 디스크 캐시 무시하고 전부 다시 합성
    python -m scripts.prewarm_tts --list   # 합성 대상 텍스트만 출력 (실제 호출 안 함)
    python -m scripts.prewarm_tts --clean  # 디스크 캐시 전체 삭제

목적:
- 서버 부팅 전에 미리 모든 시나리오 + 템플릿×메뉴/옵션 조합을 디스크에 합성해두면
  실제 운영/시연 시 첫 호출부터 즉시 응답.
- 시연이 끝나고 정리할 때는 `--clean` 한 번이면 backend/data/tts_cache/ 전체가 삭제됨.

이 스크립트는 lifespan 프리워밍과 동일한 캐시 디렉터리·동일한 합성 함수를 사용한다.
"""
import argparse
import asyncio
import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

# 프로젝트 루트를 sys.path에 추가 (스크립트를 직접 실행할 수 있도록)
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Windows + aiomysql + SSL 호환
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("prewarm_tts")

_TTS_CACHE_DIR = _ROOT / "data" / "tts_cache"


async def _collect_phrases() -> list[str]:
    """시나리오 매뉴얼의 response_text만 모아 중복 제거한 리스트 반환.
    조합 합성(템플릿/조각)은 현재 비활성이므로 DB 조회도 필요 없다."""
    from services.canned_responses import all_canned_texts

    return list(dict.fromkeys(p for p in all_canned_texts() if p))


_RATE_LIMIT_MARKERS = ("429", "RESOURCE_EXHAUSTED", "rate", "Too Many Requests")


def _is_rate_limit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(m.lower() in msg for m in _RATE_LIMIT_MARKERS)


async def _synth_one(text: str) -> Optional[bytes]:
    """단발 합성 — 예외는 그대로 위로 전파."""
    from services.chat_service import synthesize_speech
    return await synthesize_speech(text)


async def cmd_run(force: bool, delay: float, cooldown: float) -> None:
    """
    한 항목씩 합성하면서 다음 정책을 적용:
      - 정상 응답 → 다음 항목으로 (요청 간격 delay)
      - 429 발생 → cooldown(초) 일시정지 후 1회 재시도
      - 재시도까지 또 429 → 같은 항목 두 번째 cooldown 후 재시도
      - 그래도 또 429 → 일일 한도로 판단, 전체 작업 abort
    """
    from services.canned_responses import get_cached_wav, save_cached_wav

    phrases = await _collect_phrases()
    logger.info("프리워밍 대상: %d개 (요청 간격 %.1fs, 429 시 %.0fs 대기)",
                len(phrases), delay, cooldown)

    skipped = synthesized = failed = 0
    aborted = False

    for i, text in enumerate(phrases, 1):
        if not force and get_cached_wav(text) is not None:
            skipped += 1
            continue

        wav: Optional[bytes] = None
        consecutive_429 = 0
        # 같은 항목에 대해 최대 2번까지 cooldown 후 재시도
        while True:
            try:
                wav = await _synth_one(text)
                break
            except Exception as e:
                if _is_rate_limit_error(e):
                    consecutive_429 += 1
                    if consecutive_429 > 2:
                        logger.error(
                            "[%d/%d] 일일/분당 한도 초과로 보입니다. 작업을 중단합니다. (%s)",
                            i, len(phrases), text[:30],
                        )
                        aborted = True
                        break
                    logger.warning(
                        "[%d/%d] 429 감지 — %.0f초 대기 후 재시도 (%d/2): %s",
                        i, len(phrases), cooldown, consecutive_429, text[:30],
                    )
                    await asyncio.sleep(cooldown)
                    continue
                # 그 외 예외는 즉시 실패 처리
                logger.warning("[%d/%d] ERR  %s : %s", i, len(phrases), text[:30], e)
                break

        if aborted:
            failed += 1
            break

        if wav:
            save_cached_wav(text, wav)
            synthesized += 1
            logger.info("[%d/%d] OK  %s", i, len(phrases), text[:40])
        else:
            failed += 1
            logger.warning("[%d/%d] FAIL %s", i, len(phrases), text[:40])

        # 정상 합성 사이에도 짧은 sleep으로 RPM 한도 회피
        await asyncio.sleep(delay)

    logger.info(
        "%s — 합성: %d, 건너뜀: %d, 실패: %d, 남은 항목: %d",
        "중단됨" if aborted else "완료",
        synthesized, skipped, failed,
        max(0, len(phrases) - synthesized - skipped - failed),
    )


async def cmd_list() -> None:
    from services.canned_responses import get_cached_wav

    phrases = await _collect_phrases()
    print(f"# 프리워밍 대상 {len(phrases)}개")
    for p in phrases:
        cached = "v" if get_cached_wav(p) is not None else " "
        print(f"  [{cached}] {p}")


def cmd_clean() -> None:
    if not _TTS_CACHE_DIR.exists():
        logger.info("캐시 디렉터리 없음 — 삭제할 것 없음")
        return
    shutil.rmtree(_TTS_CACHE_DIR)
    logger.info("디스크 캐시 삭제 완료: %s", _TTS_CACHE_DIR)


def main():
    p = argparse.ArgumentParser(description="Gemini TTS 프리워밍 / 디스크 캐시 관리")
    p.add_argument("--force", action="store_true", help="이미 캐시된 항목도 다시 합성")
    p.add_argument("--list", action="store_true", help="합성 대상 텍스트만 출력")
    p.add_argument("--clean", action="store_true", help="디스크 캐시 전체 삭제")
    p.add_argument("--delay", type=float, default=4.5,
                   help="요청 간 지연(초). Flash TTS 무료 티어 RPM 회피용 (기본 4.5초 ≈ 13 RPM)")
    p.add_argument("--cooldown", type=float, default=60.0,
                   help="429 발생 시 일시정지 시간(초). 같은 항목에서 두 번 연속 cooldown 후에도 429면 abort")
    args = p.parse_args()

    if args.clean:
        cmd_clean()
        return
    if args.list:
        asyncio.run(cmd_list())
        return
    asyncio.run(cmd_run(force=args.force, delay=args.delay, cooldown=args.cooldown))


if __name__ == "__main__":
    main()
