"""
음성 주문(및 향후 텍스트 챗) 채팅 스키마.

응답 스키마는 Gemini의 structured output(response_schema)에 그대로 전달되므로,
필드를 함부로 추가/변경하지 말 것.
"""
from datetime import datetime
from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field


# ─── 공용 타입 ────────────────────────────────────────────────────────────────

VoicePersona = Literal["elderly", "child", "general", "unknown"]

VoiceStage = Literal[
    "greeting",
    "category_browse",
    "menu_browse",
    "menu_select",
    "option_select",
    "cart_review",
    "payment_confirm",
    "farewell",
]

ChatRole = Literal["user", "assistant", "system"]


# ─── AI Action 정의 (Discriminated Union) ────────────────────────────────────

class SpeakAction(BaseModel):
    type: Literal["speak"] = "speak"
    text: str


class NavigateAction(BaseModel):
    type: Literal["navigate"] = "navigate"
    target: Literal[
        "menu_list", "menu_detail", "category", "cart", "payment"
    ]
    category_name: Optional[str] = None
    menu_name: Optional[str] = None


class ScrollAction(BaseModel):
    type: Literal["scroll"] = "scroll"
    direction: Literal["up", "down"]


class CartAddAction(BaseModel):
    type: Literal["cart_add"] = "cart_add"
    menu_name: str
    quantity: int = 1
    option_item_ids: List[int] = Field(default_factory=list)


class OptionPreviewAction(BaseModel):
    """옵션 모달에 시각적 선택을 표시(아직 장바구니엔 안 담음). 사용자가 옵션을 골랐을 때 화면 피드백용."""
    type: Literal["option_preview"] = "option_preview"
    menu_name: str
    option_item_ids: List[int] = Field(default_factory=list)


class CartRemoveAction(BaseModel):
    type: Literal["cart_remove"] = "cart_remove"
    menu_name: str


class CartUpdateAction(BaseModel):
    type: Literal["cart_update"] = "cart_update"
    menu_name: str
    quantity: int


class PlaceOrderAction(BaseModel):
    type: Literal["place_order"] = "place_order"


class EndConversationAction(BaseModel):
    type: Literal["end_conversation"] = "end_conversation"


AIAction = Annotated[
    Union[
        SpeakAction,
        NavigateAction,
        ScrollAction,
        CartAddAction,
        OptionPreviewAction,
        CartRemoveAction,
        CartUpdateAction,
        PlaceOrderAction,
        EndConversationAction,
    ],
    Field(discriminator="type"),
]


# ─── AI 응답 스키마 (Gemini structured output) ───────────────────────────────

class AIChatResponse(BaseModel):
    intent: str = Field(description="사용자의 의도 분류 키 (예: order_menu, ask_recommendation, end)")
    response_text: str = Field(description="사용자에게 음성/텍스트로 전달할 답변")
    next_stage: Optional[VoiceStage] = None
    actions: List[AIAction] = Field(default_factory=list)
    requires_user_input: bool = True
    end_conversation: bool = False
    # (현재 비활성) 조합형 응답용 음성 조각 배열. 백엔드가 무시하고 response_text를 통째 합성한다.
    # AI는 이 필드를 채우지 말 것.
    audio_segments: Optional[List[str]] = None


# ─── 카트 스냅샷 (요청에 동봉되어 컨텍스트로 사용) ───────────────────────────

class CartItemSnapshot(BaseModel):
    menu_name: str
    quantity: int
    unit_price: int
    option_names: List[str] = Field(default_factory=list)


# ─── 요청/응답 ───────────────────────────────────────────────────────────────

class VoiceStartRequest(BaseModel):
    session_uuid: str


class VoiceStartResponse(BaseModel):
    session_uuid: str
    persona: VoicePersona
    current_stage: VoiceStage
    attempt_started_at: datetime
    greeting: AIChatResponse
    audio_b64: Optional[str] = None


class VoiceMessageRequest(BaseModel):
    session_uuid: str
    content: str
    cart_snapshot: Optional[List[CartItemSnapshot]] = None
    # 프런트가 현재 화면 상태를 같이 보내면 백엔드가 해당 컨텍스트를 DB에서 조회해 주입한다.
    selected_category: Optional[str] = None
    selected_menu_name: Optional[str] = None


class VoiceMessageResponse(BaseModel):
    session_uuid: str
    persona: VoicePersona
    current_stage: VoiceStage
    matched_by: str  # pattern / menu_name / gemini / cached
    response: AIChatResponse
    # 응답 텍스트의 TTS 오디오를 base64 WAV로 인라인 — 별도 /voice/tts 호출 1회 절약
    audio_b64: Optional[str] = None


class VoiceEndRequest(BaseModel):
    session_uuid: str


class VoiceEndResponse(BaseModel):
    session_uuid: str
    ended: bool


class ChatMessageItem(BaseModel):
    id: int
    role: ChatRole
    content: str
    intent: Optional[str] = None
    matched_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
