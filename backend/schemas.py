from datetime import datetime
from typing import Annotated, Any, Dict, Generic, List, Literal, Optional, TypeVar, Union

from pydantic import BaseModel, Field

from core.enums import OrderStatus, ServingTemperature, SessionEndReason, SessionStatus


# ============================================================================
# Common
# ============================================================================


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def make_error(code: str, message: str, **details) -> Dict[str, Any]:
    return ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details or None)
    ).model_dump()


# ============================================================================
# Kiosk / Session
# ============================================================================


class KioskCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["1층 로비 키오스크"])
    location: Optional[str] = Field(None, max_length=200, examples=["서울 강남점 1층 입구"])


class KioskUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    location: Optional[str] = Field(None, max_length=200)
    is_active: Optional[bool] = None


class KioskListRequest(BaseModel):
    is_active: Optional[bool] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class KioskResponse(BaseModel):
    id: int
    name: str
    location: Optional[str] = None
    is_active: bool
    registered_at: datetime
    last_seen_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class KioskCreateResponse(KioskResponse):
    api_key: str


class SessionListRequest(BaseModel):
    status: Optional[SessionStatus] = None
    kiosk_id: Optional[int] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class SessionUpdateRequest(BaseModel):
    status: Optional[SessionStatus] = None
    end_reason: Optional[SessionEndReason] = None
    is_simple_mode: Optional[bool] = None
    estimated_age_group: Optional[str] = Field(None, max_length=20)
    estimated_gender: Optional[str] = Field(None, max_length=10)
    help_triggered: Optional[bool] = None


class SessionResponse(BaseModel):
    session_uuid: str
    kiosk_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    end_reason: Optional[str] = None
    is_simple_mode: bool
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
    help_triggered: bool
    status: str

    model_config = {"from_attributes": True}


# ============================================================================
# Menu / Option / Order
# ============================================================================


class MenuListRequest(BaseModel):
    category_name: Optional[str] = Field(None, description="카테고리 이름으로 필터링")
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)
    sort_by: str = Field("name")
    sort_order: str = Field("asc", pattern="^(asc|desc)$")
    include_unavailable: bool = False


class CategoryListRequest(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class MenuCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1)
    price: int = Field(..., ge=0)
    icon_emoji: Optional[str] = Field(None, max_length=10)
    calories: Optional[int] = Field(None, ge=0)
    serving_temperature: Optional[ServingTemperature] = None
    is_caffeinated: bool = False
    description: Optional[str] = Field(None, max_length=255)
    image_url: Optional[str] = Field(None, max_length=500)


class MenuUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, min_length=1)
    price: Optional[int] = Field(None, ge=0)
    icon_emoji: Optional[str] = Field(None, max_length=10)
    calories: Optional[int] = Field(None, ge=0)
    serving_temperature: Optional[ServingTemperature] = None
    is_caffeinated: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=255)
    image_url: Optional[str] = Field(None, max_length=500)
    is_available: Optional[bool] = None


class AvailabilityUpdateRequest(BaseModel):
    is_available: bool


class OptionItemResponse(BaseModel):
    id: int
    name: str
    extra_price: int
    is_default: bool
    is_available: bool

    model_config = {"from_attributes": True}


class OptionGroupResponse(BaseModel):
    id: int
    name: str
    is_required: bool
    min_select: int
    max_select: int
    items: List[OptionItemResponse] = []

    model_config = {"from_attributes": True}


class CategoryResponse(BaseModel):
    id: int
    name: str
    display_order: int = 0

    model_config = {"from_attributes": True}


class MenuListResponse(BaseModel):
    id: int
    name: str
    category: str
    price: int
    icon_emoji: Optional[str] = None
    calories: Optional[int] = None
    serving_temperature: Optional[str] = None
    is_caffeinated: bool = False
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool

    model_config = {"from_attributes": True}


class MenuDetailResponse(MenuListResponse):
    option_groups: List[OptionGroupResponse]


class OptionItemUpsertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    extra_price: int = Field(0, ge=0)
    is_default: bool = False
    is_available: bool = True
    option_order: int = Field(0, ge=0)


class OptionGroupUpsertRequest(BaseModel):
    menu_name: Optional[str] = Field(None, min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=50)
    group_order: int = Field(0, ge=0)
    is_required: bool = True
    min_select: int = Field(1, ge=0)
    max_select: int = Field(1, ge=1)
    items: List[OptionItemUpsertRequest] = Field(default_factory=list)


class OptionGroupListRequest(BaseModel):
    menu_name: Optional[str] = Field(None, min_length=1, max_length=100)
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class SelectedOptionRequest(BaseModel):
    option_item_id: int = Field(..., gt=0, examples=[2])


class CartItemRequest(BaseModel):
    menu_name: str = Field(..., min_length=1, examples=["아이스 아메리카노"])
    quantity: int = Field(default=1, ge=1, le=99, examples=[2])
    from_recommendation: bool = Field(default=False)
    selected_options: List[SelectedOptionRequest] = Field(
        default_factory=list,
        examples=[[{"option_item_id": 2}]],
    )


class CartReplaceRequest(BaseModel):
    items: List[CartItemRequest] = Field(default_factory=list)


class CartOptionResponse(BaseModel):
    option_item_id: int
    option_name: str
    extra_price: int


class CartItemResponse(BaseModel):
    line_id: str
    menu_id: int
    menu_name: str
    quantity: int
    unit_price: int
    line_total: int
    from_recommendation: bool
    options: List[CartOptionResponse] = []


class CartResponse(BaseModel):
    session_uuid: str
    status: str
    item_count: int
    total_quantity: int
    total_price: int
    contains_recommendation_item: bool
    items: List[CartItemResponse]
    created_at: datetime
    updated_at: datetime


class OrderItemRequest(BaseModel):
    menu_name: str = Field(..., min_length=1, examples=["아이스 아메리카노"])
    quantity: int = Field(default=1, ge=1, le=99, examples=[2])
    unit_price: int = Field(..., ge=0, examples=[5000], description="프런트 계산값 (서버에서 재검증)")
    from_recommendation: bool = Field(default=False)
    selected_options: List[SelectedOptionRequest] = Field(
        default_factory=list,
        examples=[[{"option_item_id": 2}]],
    )


class OrderCreateRequest(BaseModel):
    session_uuid: str = Field(..., min_length=32, max_length=32)
    items: Optional[List[OrderItemRequest]] = Field(
        default=None,
        description="생략 시 서버에 저장된 cart를 기준으로 주문 생성",
    )
    used_recommendation: Optional[bool] = Field(default=None)


class OrderListRequest(BaseModel):
    status: Optional[OrderStatus] = None
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class OrderItemOptionResponse(BaseModel):
    option_name: str
    extra_price: int

    model_config = {"from_attributes": True}


class OrderItemResponse(BaseModel):
    id: int
    menu_name: str
    quantity: int
    unit_price: int
    from_recommendation: bool
    options: List[OrderItemOptionResponse] = []

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    order_uuid: str
    session_uuid: str
    created_at: datetime
    total_price: int
    used_recommendation: bool
    status: str
    items: List[OrderItemResponse]

    model_config = {"from_attributes": True}


# ============================================================================
# Vision / Face / Analytics / Recommendation
# ============================================================================


class AnalyticsRangeRequest(BaseModel):
    start_date: Optional[datetime] = Field(None, description="시작 시각 (포함)")
    end_date: Optional[datetime] = Field(None, description="종료 시각 (미포함)")
    kiosk_id: Optional[int] = Field(None, description="특정 키오스크만 필터")


class SessionAnalytics(BaseModel):
    total_sessions: int
    simple_mode_sessions: int
    simple_mode_rate: float
    help_triggered_count: int


class RecommendationAnalytics(BaseModel):
    total_shown: int
    total_clicked: int
    click_through_rate: float
    led_to_order_count: int
    order_conversion_rate: float


class OrderAnalytics(BaseModel):
    total_orders: int
    total_revenue: int
    avg_order_price: float
    recommendation_used_count: int
    recommendation_used_rate: float


class FaceAnalyzeRequest(BaseModel):
    session_uuid: str = Field(..., min_length=32, max_length=32)
    frames: List[str] = Field(..., min_length=1, description="Base64 인코딩된 JPEG 프레임 목록")


class FaceAnalyzeResponse(BaseModel):
    session_uuid: str
    age_group: str
    gender: str
    age_est: int
    confidence: float
    should_use_simple_mode: bool
    analyzed_at: datetime


class VisionEventCreate(BaseModel):
    low_light_corrected: bool = False
    detected_people_count: int = 0
    masked_faces_count: int = 0
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
    age_confidence: Optional[float] = None
    confusion_detected: bool = False


class VisionEventResponse(BaseModel):
    id: int
    session_id: int
    created_at: datetime
    low_light_corrected: bool
    detected_people_count: int
    masked_faces_count: int
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None
    age_confidence: Optional[float] = None
    confusion_detected: bool

    model_config = {"from_attributes": True}


class SimpleModeDecision(BaseModel):
    should_use_simple_mode: bool
    estimated_age_group: Optional[str] = None
    estimated_gender: Optional[str] = None


class RecommendationItemResponse(BaseModel):
    rank: int = Field(..., description="추천 순위")
    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")
    count: Optional[int] = Field(None, description="주문 횟수")
    popularity: Optional[float] = Field(None, description="인기도(0~1)")
    trend_weight: Optional[float] = Field(None, description="트렌드 가중치")
    final_score: Optional[float] = Field(None, description="최종 점수")
    copurchase_count: Optional[int] = Field(None, description="함께 구매된 횟수")
    strength: Optional[float] = Field(None, description="추천 강도")
    frequency: Optional[str] = Field(None, description="비율 문자열")
    reasoning: Optional[str] = Field(None, description="추천 이유")


class SelectedMenuResponse(BaseModel):
    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")


class ModeAResponse(BaseModel):
    mode: str = Field(default="A", description="추천 모드")
    situation: str = Field(..., description="상황 설명")
    recommendations: List[RecommendationItemResponse] = Field(..., description="추천 목록")
    total_orders: int = Field(..., description="해당 상황의 주문 수")
    total_items: Optional[int] = Field(None, description="해당 상황의 아이템 수")
    cache_hit: Optional[bool] = Field(None, description="캐시 적중 여부")


class CFScoreBreakdown(BaseModel):
    profile_popularity: float = Field(..., description="프로필 인기도")
    global_popularity: float = Field(..., description="전체 평균 인기도")
    base_score: Optional[float] = Field(None, description="프로필/전체 인기도 보정 점수")
    cart_cf_score: Optional[float] = Field(None, description="장바구니 기반 협업 필터링 점수")
    cf_score: float = Field(..., description="CF 점수")
    cart_support_count: Optional[int] = Field(None, description="근거가 된 장바구니 메뉴 수")
    cart_support_ratio: Optional[float] = Field(None, description="장바구니 근거 비율")


class IntegratedRecommendationItem(BaseModel):
    rank: int = Field(..., description="추천 순위")
    menu_id: int = Field(..., description="메뉴 ID")
    menu_name: str = Field(..., description="메뉴 이름")
    cf_breakdown: CFScoreBreakdown = Field(..., description="CF 점수 분해")
    trend_score: float = Field(..., description="트렌드 가중치")
    final_score: float = Field(..., description="최종 점수")
    reasoning: str = Field(..., description="추천 이유")


class SuggestRequest(BaseModel):
    gender: str = Field(..., description="M 또는 F")
    age: int = Field(..., ge=15, le=100, description="사용자 나이")
    cart_items: List[int] = Field(default_factory=list, description="장바구니 메뉴 ID 목록")
    top_n: Optional[int] = Field(5, ge=1, le=10, description="추천 개수")
    include_trend: Optional[bool] = Field(True, description="트렌드 반영 여부")


class SuggestResponse(BaseModel):
    mode: str = Field(default="CF", description="추천 모드")
    user_context: dict = Field(..., description="사용자 문맥")
    cart_items: List[SelectedMenuResponse] = Field(..., description="장바구니 메뉴 목록")
    recommendations: List[IntegratedRecommendationItem] = Field(..., description="추천 목록")
    cache_hit: Optional[bool] = Field(None, description="캐시 적중 여부")


# ============================================================================
# Session Activity Logs
# ============================================================================


class ActivityLogItemRequest(BaseModel):
    seq: int = Field(..., ge=1)
    occurred_at: datetime
    event_type: str = Field(..., min_length=1, max_length=30)
    screen_name: Optional[str] = Field(None, max_length=30)
    action_name: str = Field(..., min_length=1, max_length=50)
    target_type: Optional[str] = Field(None, max_length=30)
    target_id: Optional[str] = Field(None, max_length=100)
    target_label: Optional[str] = Field(None, max_length=200)
    duration_ms: Optional[int] = Field(None, ge=0)
    source: str = Field(default="ui", min_length=1, max_length=20)
    payload_json: Optional[Dict[str, Any]] = None


class ActivityLogBatchRequest(BaseModel):
    session_uuid: str = Field(..., min_length=32, max_length=32)
    events: List[ActivityLogItemRequest] = Field(default_factory=list)


class ActivityLogBatchResponse(BaseModel):
    session_uuid: str
    inserted_count: int


# ============================================================================
# Chat / Voice
# ============================================================================


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


class SpeakAction(BaseModel):
    type: Literal["speak"] = "speak"
    text: str


class NavigateAction(BaseModel):
    type: Literal["navigate"] = "navigate"
    target: Literal["menu_list", "menu_detail", "category", "cart", "payment"]
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
    type: Literal["option_preview"] = "option_preview"
    menu_name: str
    option_item_ids: List[int] = Field(default_factory=list)


class CartRemoveAction(BaseModel):
    type: Literal["cart_remove"] = "cart_remove"
    menu_name: str
    cart_line_id: Optional[str] = None
    option_item_ids: List[int] = Field(default_factory=list)


class CartUpdateAction(BaseModel):
    type: Literal["cart_update"] = "cart_update"
    menu_name: str
    quantity: int
    cart_line_id: Optional[str] = None
    option_item_ids: List[int] = Field(default_factory=list)


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


class AIChatResponse(BaseModel):
    intent: str = Field(description="사용자의 의도 분류 키 (예: order_menu, ask_recommendation, end)")
    response_text: str = Field(description="사용자에게 음성/텍스트로 전달할 답변")
    next_stage: Optional[VoiceStage] = None
    actions: List[AIAction] = Field(default_factory=list)
    requires_user_input: bool = True
    end_conversation: bool = False


class CartItemSnapshot(BaseModel):
    line_id: Optional[str] = None
    menu_name: str
    quantity: int
    unit_price: int
    option_item_ids: List[int] = Field(default_factory=list)
    option_names: List[str] = Field(default_factory=list)


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
    selected_category: Optional[str] = None
    selected_menu_name: Optional[str] = None


class VoiceMessageResponse(BaseModel):
    session_uuid: str
    persona: VoicePersona
    current_stage: VoiceStage
    matched_by: str
    response: AIChatResponse
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
