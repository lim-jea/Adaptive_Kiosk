"""음성 주문 파이프라인의 핵심 분기(정제→canned→pattern→menu 매칭)를 빠르게 검증.

- DB 없이도 확인 가능한 범위만 다룬다.
- 서버 실행/HTTP 호출은 하지 않는다.

실행 예:
  python backend/scripts/verify_voice_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_import_path() -> None:
    # repo root에서 실행해도 backend 패키지 import가 되도록 보정
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def _summarize(resp) -> dict:
    if resp is None:
        return {"matched": False}
    return {
        "matched": True,
        "intent": getattr(resp, "intent", None),
        "next_stage": getattr(resp, "next_stage", None),
        "end_conversation": getattr(resp, "end_conversation", None),
        "requires_user_input": getattr(resp, "requires_user_input", None),
        "response_text": getattr(resp, "response_text", None),
    }


def main() -> int:
    _bootstrap_import_path()

    from services.canned_responses import match_canned
    from services.voice_matching import sanitize_input, match_pattern, match_menu_name

    fake_menus = [
        "아이스 아메리카노",
        "따뜻한 아메리카노",
        "카페라떼",
        "딸기 스무디",
        "레몬에이드",
        "드립 커피",
        "캐모마일 티",
    ]

    cases = [
        # (stage, utterance)
        ("greeting", "안녕"),
        ("menu_browse", "추천해줘"),
        ("option_select", "취소"),
        ("option_select", "전체 취소"),
        ("menu_browse", "아아"),
        ("menu_browse", "아이스 아메리카노 주세요"),
        ("menu_browse", "음...,,  카페라떼!"),
        # 카테고리 단어가 메뉴명에 포함된 케이스: 카테고리 canned가 가로채면 안 됨
        ("menu_browse", "딸기 스무디"),
        ("menu_browse", "레몬에이드"),
        ("menu_browse", "드립 커피"),
        ("menu_browse", "캐모마일 티"),
    ]

    print("== Voice pipeline quick verify ==")
    for stage, utter in cases:
        sanitized = sanitize_input(utter)
        canned = match_canned(sanitized, stage)
        pattern = match_pattern(sanitized, purpose="voice_order", stage=stage) if canned is None else None
        menu = match_menu_name(sanitized, fake_menus) if (canned is None and pattern is None) else None

        print("\n---")
        print(f"stage={stage} | raw={utter!r} | sanitized={sanitized!r}")
        print("canned :", _summarize(canned))
        print("pattern:", _summarize(pattern))
        print("menu   :", _summarize(menu))

    # 핵심 기대치(실패하면 출력으로 확인)
    print("\n== Expectations ==")
    print("- '취소' 단독 발화는 canned(cancel)을 타지 않고 pattern(cancel)로 가야 함")
    print("- '전체 취소'는 canned(cancel)로 매칭되어 end_conversation=true 여야 함")
    print("- 메뉴명 매칭 응답은 navigate(menu_detail) + speak 중심으로 생성되어야 함")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
