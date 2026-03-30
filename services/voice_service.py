import re
import logging
from typing import Optional, List

from google import genai
from core.config import settings

logger = logging.getLogger(__name__)

# ─── Gemini 초기화 ───
_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None and settings.GENAI_API_KEY:
        _gemini_client = genai.Client(api_key=settings.GENAI_API_KEY)
    return _gemini_client


# ─── 전처리: 패턴 매칭 ───
# 빠르게 판별 가능한 패턴들 (정규식 + 의도)
INTENT_PATTERNS = [
    # 긍정 (주문하겠다)
    (r"(네|예|응|좋아|할게|할래|주문|시작|해줘|해 줘|부탁)", "order_confirm"),
    # 부정 (주문 안 하겠다)
    (r"(아니|싫어|안 할|안할|괜찮|됐어|필요 없|필요없)", "order_decline"),
    # 도움 요청
    (r"(도와|도움|모르겠|어떻게|뭐가 있|뭐 있|추천|알려)", "help"),
    # 취소
    (r"(취소|그만|중단|멈춰|나갈)", "cancel"),
    # 메뉴 언급 (커피, 라떼 등 키워드)
    (r"(아메리카노|라떼|카페|커피|에이드|주스|티|차|스무디|초코|모카|바닐라|캐러멜)", "menu_mention"),
    # 확인/동의
    (r"(맞아|그래|맞습니다|그걸로|그거)", "confirm"),
]


def match_pattern(text: str) -> Optional[str]:
    """
    STT 텍스트에서 패턴 매칭으로 의도를 추출합니다.
    매칭되면 intent 문자열, 안 되면 None.
    """
    text = text.strip().lower()
    for pattern, intent in INTENT_PATTERNS:
        if re.search(pattern, text):
            return intent
    return None


# ─── 패턴 매칭 결과에 따른 즉시 응답 ───
PATTERN_RESPONSES = {
    "order_confirm": {
        "response_text": "네, 주문을 도와드리겠습니다. 어떤 음료를 원하시나요? 커피, 라떼, 에이드, 티 중에서 골라주세요.",
        "requires_followup": True,
    },
    "order_decline": {
        "response_text": "알겠습니다. 필요하시면 언제든 말씀해 주세요.",
        "requires_followup": False,
    },
    "help": {
        "response_text": "도움을 드리겠습니다. 저희 매장에는 커피, 라떼, 에이드, 티 종류가 있어요. 어떤 종류를 좋아하시나요?",
        "requires_followup": True,
    },
    "cancel": {
        "response_text": "주문을 취소하겠습니다. 화면으로 돌아갈게요.",
        "requires_followup": False,
    },
    "menu_mention": {
        "response_text": "해당 메뉴를 선택하시겠어요? 맞으시면 '네'라고 말씀해 주세요.",
        "requires_followup": True,
    },
    "confirm": {
        "response_text": "확인했습니다. 주문을 진행할게요.",
        "requires_followup": False,
    },
}


def get_pattern_response(intent: str) -> dict:
    """패턴 매칭된 의도에 대한 즉시 응답을 반환합니다."""
    return PATTERN_RESPONSES.get(intent, {
        "response_text": "죄송합니다. 다시 한 번 말씀해 주시겠어요?",
        "requires_followup": True,
    })


# ─── Gemini 호출 (패턴 매칭 실패 시) ───
GEMINI_SYSTEM_PROMPT = """
너는 키오스크 음성 주문 도우미야. 고령층이나 디지털 취약계층이 음성으로 음료를 주문하는 것을 돕는 역할이야.

규칙:
1. 반드시 한국어로, 짧고 쉬운 문장으로 답해. (2문장 이내)
2. 존댓말을 사용해.
3. 아래 시나리오 중 하나에 맞춰 응답해:
   - 사용자가 주문 의사를 밝히면 → 음료 종류(커피, 라떼, 에이드, 티)를 물어봐
   - 사용자가 음료 이름을 말하면 → 확인 질문을 해 ("아메리카노 한 잔 맞으신가요?")
   - 사용자가 확인하면 → "주문을 완료하겠습니다"로 마무리
   - 사용자가 거부하면 → "알겠습니다. 화면으로 돌아갈게요"
   - 사용자가 모르겠다고 하면 → 추천을 제안해
   - 이해할 수 없는 말이면 → "죄송합니다. 다시 한 번 말씀해 주시겠어요?"

4. 응답 형식: 반드시 아래 형식으로만 답해.
   intent: (order_confirm|order_decline|help|cancel|menu_mention|confirm|unknown)
   response: (응답 텍스트)
   followup: (true|false)
"""


async def ask_gemini(stt_text: str, conversation_history: str = "") -> dict:
    """
    Gemini Flash Lite에 시나리오 기반 요청을 보냅니다.
    전처리 패턴 매칭 실패 시에만 호출됩니다.
    """
    client = _get_gemini_client()
    if client is None:
        return {
            "intent": "unknown",
            "response_text": "죄송합니다. 다시 한 번 말씀해 주시겠어요?",
            "requires_followup": True,
        }

    prompt = f"{GEMINI_SYSTEM_PROMPT}\n\n"
    if conversation_history:
        prompt += f"이전 대화:\n{conversation_history}\n\n"
    prompt += f"사용자: {stt_text}\n\n응답:"

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
        )
        return _parse_gemini_response(response.text)
    except Exception as e:
        logger.error("Gemini API error: %s", e)
        return {
            "intent": "unknown",
            "response_text": "죄송합니다. 잠시 문제가 생겼어요. 다시 말씀해 주시겠어요?",
            "requires_followup": True,
        }


def _parse_gemini_response(raw: str) -> dict:
    """Gemini 응답을 파싱하여 구조화합니다."""
    intent = "unknown"
    response_text = "죄송합니다. 다시 한 번 말씀해 주시겠어요?"
    requires_followup = True

    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.lower().startswith("intent:"):
            intent = line.split(":", 1)[1].strip()
        elif line.lower().startswith("response:"):
            response_text = line.split(":", 1)[1].strip()
        elif line.lower().startswith("followup:"):
            requires_followup = line.split(":", 1)[1].strip().lower() == "true"

    return {
        "intent": intent,
        "response_text": response_text,
        "requires_followup": requires_followup,
    }


# ─── 메인 처리 함수 ───
async def process_voice_input(stt_text: str, conversation_history: str = "") -> dict:
    """
    음성 입력을 처리합니다.
    1. 패턴 매칭 시도 → 성공하면 즉시 응답
    2. 실패하면 Gemini Flash Lite 호출
    """
    # 1단계: 패턴 매칭
    intent = match_pattern(stt_text)
    if intent is not None:
        resp = get_pattern_response(intent)
        return {
            "intent": intent,
            "matched_by": "pattern",
            "response_text": resp["response_text"],
            "requires_followup": resp["requires_followup"],
        }

    # 2단계: Gemini 호출
    result = await ask_gemini(stt_text, conversation_history)
    return {
        "intent": result["intent"],
        "matched_by": "gemini",
        "response_text": result["response_text"],
        "requires_followup": result["requires_followup"],
    }
