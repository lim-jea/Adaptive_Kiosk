# 프론트엔드 API 링크 정리

작성일: 2026-04-29  
기준 코드: `backend/main.py`, `backend/api/v1/router.py`, `backend/api/v1/endpoints/*`, `backend/schemas.py`

이 문서는 프런트엔드 개발 시 기준으로 사용할 백엔드 API 목록이다. 별도 언급이 없으면 모든 API의 기본 prefix는 `/api/v1`이다.

## 1. 기본 정보

### Base URL

개발 환경에서는 실행 방식에 따라 아래 중 하나를 사용한다.

```text
http://localhost:5000
http://127.0.0.1:5000
```

프런트에서 호출할 때는 아래처럼 조합한다.

```text
{BASE_URL}/api/v1/{resource}
```

예:

```text
GET http://localhost:5000/api/v1/menus
```

### 공통 응답 형식

목록 API는 대부분 아래 페이지네이션 형식을 반환한다.

```json
{
  "items": [],
  "total": 0,
  "skip": 0,
  "limit": 100
}
```

에러 응답은 API에 따라 두 형태가 섞여 있다.

```json
{
  "detail": {
    "error": {
      "code": "SESSION_NOT_FOUND",
      "message": "Session not found",
      "details": {
        "session_uuid": "..."
      }
    }
  }
}
```

일부 추천 API는 문자열 detail을 반환한다.

```json
{
  "detail": "Recommendation engine not initialized"
}
```

### 인증 방식

#### 키오스크 인증: `X-API-Key`

실제 키오스크 단말이 세션을 생성하거나 자신의 정보를 조회할 때 사용한다.

```http
X-API-Key: {kiosk_api_key}
```

대상 API:

- `POST /api/v1/sessions`
- `GET /api/v1/kiosks/me`

#### 관리자 인증: HTTP Basic Auth

관리자용 등록/목록/통계/쓰기 API에서 사용한다. `.env`의 `KIOSK_USERNAME`, `KIOSK_PASSWORD` 값과 비교한다.

대상 API:

- `POST /api/v1/kiosks`
- `GET /api/v1/kiosks`
- `GET /api/v1/sessions`
- `POST /api/v1/menus`
- `POST /api/v1/option-groups`
- `POST /api/v1/menus/{menu_name}/option-groups`
- `GET /api/v1/analytics/sessions`
- `GET /api/v1/analytics/recommendations`
- `GET /api/v1/analytics/orders`
- `/docs`, `/redoc`

### 공통 enum

```text
SessionStatus: active | ended | abandoned
SessionEndReason: completed | timeout | cancelled
OrderStatus: pending | completed | cancelled
ServingTemperature: hot | cold | both
VoicePersona: elderly | child | general | unknown
VoiceStage: greeting | category_browse | menu_browse | menu_select | option_select | cart_review | payment_confirm | farewell
```

## 2. 루트/상태 API

### GET `/`

서버 실행 여부를 간단히 확인한다.

인증: 없음

응답:

```json
{
  "message": "Adaptive Kiosk API is running"
}
```

### GET `/health`

헬스 체크용 API.

인증: 없음

응답:

```json
{
  "status": "ok"
}
```

## 3. Kiosk API

키오스크 단말 등록, 목록 조회, 현재 단말 조회 API.

### POST `/api/v1/kiosks`

키오스크를 새로 등록하고 API Key를 발급한다.

인증: 관리자 Basic Auth

Request Body:

```json
{
  "name": "1층 로비 키오스크",
  "location": "서울 강남 1층 입구"
}
```

필드:

- `name`: string, 필수, 1~100자
- `location`: string 또는 null, 선택, 최대 200자

Response `201`:

```json
{
  "id": 1,
  "name": "1층 로비 키오스크",
  "location": "서울 강남 1층 입구",
  "is_active": true,
  "registered_at": "2026-04-29T04:00:00Z",
  "last_seen_at": null,
  "api_key": "발급된_API_KEY"
}
```

프런트 역할:

- 관리자 화면에서 신규 키오스크 등록 시 사용
- 반환된 `api_key`는 키오스크 단말 설정에 저장해야 한다

### GET `/api/v1/kiosks`

키오스크 목록을 조회한다.

인증: 관리자 Basic Auth

Query:

- `is_active`: boolean, 선택
- `skip`: number, 기본 `0`
- `limit`: number, 기본 `100`, 최대 `1000`

예:

```text
GET /api/v1/kiosks?is_active=true&skip=0&limit=100
```

Response `200`:

```json
{
  "items": [
    {
      "id": 1,
      "name": "1층 로비 키오스크",
      "location": "서울 강남 1층 입구",
      "is_active": true,
      "registered_at": "2026-04-29T04:00:00Z",
      "last_seen_at": null
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

### GET `/api/v1/kiosks/me`

현재 `X-API-Key`로 인증된 키오스크 정보를 조회한다.

인증: `X-API-Key`

Response `200`: `KioskResponse`

주요 에러:

- `401 INVALID_API_KEY`: API Key가 없거나 비활성 키오스크

프런트 역할:

- 키오스크 앱 부팅 시 저장된 API Key가 유효한지 확인
- 화면 상단/관리 정보에 단말명 표시

## 4. Session API

키오스크 사용자의 주문 세션을 생성, 조회, 업데이트한다.

### POST `/api/v1/sessions`

새 사용자 세션을 생성한다. 생성 시 서버에서 해당 세션의 장바구니도 같이 준비한다.

인증: `X-API-Key`

Request Body: 없음

Response `201`:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "kiosk_id": 1,
  "started_at": "2026-04-29T04:00:00Z",
  "ended_at": null,
  "end_reason": null,
  "is_simple_mode": false,
  "estimated_age_group": null,
  "estimated_gender": null,
  "help_triggered": false,
  "status": "active"
}
```

프런트 역할:

- 키오스크 첫 화면 진입 또는 주문 시작 버튼 클릭 시 호출
- 이후 대부분의 API에 `session_uuid`를 전달한다

### GET `/api/v1/sessions`

세션 목록을 조회한다.

인증: 관리자 Basic Auth

Query:

- `status`: `active | ended | abandoned`, 선택
- `kiosk_id`: number, 선택
- `skip`: number, 기본 `0`
- `limit`: number, 기본 `100`, 최대 `1000`

Response `200`: `PaginatedResponse<SessionResponse>`

프런트 역할:

- 관리자 세션 모니터링 화면
- 특정 키오스크/상태별 세션 필터링

### GET `/api/v1/sessions/{session_uuid}`

세션 단건을 조회한다.

인증: 없음

Path:

- `session_uuid`: string

Response `200`: `SessionResponse`

주요 에러:

- `404 SESSION_NOT_FOUND`

프런트 역할:

- 현재 세션 상태 동기화
- 간편모드 전환 여부, 종료 여부 확인

### PATCH `/api/v1/sessions/{session_uuid}`

세션 상태나 간편모드 관련 값을 업데이트한다.

인증: 없음

Request Body:

```json
{
  "status": "ended",
  "end_reason": "completed",
  "is_simple_mode": true,
  "estimated_age_group": "60+",
  "estimated_gender": "F",
  "help_triggered": false
}
```

모든 필드는 선택이다.

필드:

- `status`: `active | ended | abandoned`
- `end_reason`: `completed | timeout | cancelled`
- `is_simple_mode`: boolean
- `estimated_age_group`: string 또는 null
- `estimated_gender`: string 또는 null
- `help_triggered`: boolean

Response `200`: `SessionResponse`

프런트 역할:

- 주문 완료/취소/타임아웃 시 세션 종료 처리
- 사용자가 도움 버튼을 눌렀을 때 `help_triggered` 기록
- 얼굴 분석 결과와 별개로 UI에서 간편모드를 수동 전환할 때 사용

## 5. Menu API

카테고리, 메뉴 목록, 메뉴 상세, 메뉴 생성 API.

### GET `/api/v1/categories`

카테고리 목록을 조회한다.

인증: 없음

Query:

- `skip`: number, 기본 `0`
- `limit`: number, 기본 `100`, 최대 `1000`

Response `200`:

```json
{
  "items": [
    {
      "id": 1,
      "name": "커피",
      "display_order": 0
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

프런트 역할:

- 메뉴 탭/카테고리 필터 구성

### GET `/api/v1/menus`

메뉴 목록을 조회한다. 카테고리 필터, 페이지네이션, 정렬을 지원한다.

인증: 없음

Query:

- `category_name`: string, 선택
- `skip`: number, 기본 `0`
- `limit`: number, 기본 `100`, 최대 `1000`
- `sort_by`: string, 기본 `name`
- `sort_order`: `asc | desc`, 기본 `asc`

예:

```text
GET /api/v1/menus?category_name=커피&sort_by=price&sort_order=asc
```

Response `200`:

```json
{
  "items": [
    {
      "id": 1,
      "name": "아이스 아메리카노",
      "category": "커피",
      "price": 4500,
      "icon_emoji": "☕",
      "calories": 10,
      "serving_temperature": "cold",
      "is_caffeinated": true,
      "description": "깔끔한 아이스 커피",
      "image_url": "/static/menus/americano.png",
      "is_available": true
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

프런트 역할:

- 메뉴 그리드 렌더링
- 추천 결과의 `menu_id`, `menu_name`과 매칭해 카드 표시

### POST `/api/v1/menus`

메뉴를 새로 생성한다.

인증: 관리자 Basic Auth

Request Body:

```json
{
  "name": "아이스 아메리카노",
  "category": "커피",
  "price": 4500,
  "icon_emoji": "☕",
  "calories": 10,
  "serving_temperature": "cold",
  "is_caffeinated": true,
  "description": "깔끔한 아이스 커피",
  "image_url": "/static/menus/americano.png"
}
```

Response `201`: `MenuListResponse`

프런트 역할:

- 관리자 메뉴 등록 화면

### GET `/api/v1/menus/{menu_name}`

메뉴 상세와 옵션 그룹을 조회한다.

인증: 없음

Path:

- `menu_name`: 메뉴명

Response `200`:

```json
{
  "id": 1,
  "name": "아이스 아메리카노",
  "category": "커피",
  "price": 4500,
  "icon_emoji": "☕",
  "calories": 10,
  "serving_temperature": "cold",
  "is_caffeinated": true,
  "description": "깔끔한 아이스 커피",
  "image_url": "/static/menus/americano.png",
  "is_available": true,
  "option_groups": [
    {
      "id": 1,
      "name": "사이즈",
      "is_required": true,
      "min_select": 1,
      "max_select": 1,
      "items": [
        {
          "id": 2,
          "name": "Large",
          "extra_price": 500,
          "is_default": false,
          "is_available": true
        }
      ]
    }
  ]
}
```

주요 에러:

- `404 MENU_NOT_FOUND`

프런트 역할:

- 메뉴 상세 페이지
- 옵션 선택 UI 구성

## 6. Option API

메뉴 옵션 그룹과 옵션 항목을 조회/생성/갱신한다.

### GET `/api/v1/option-groups`

옵션 그룹 목록을 조회한다.

인증: 없음

Query:

- `menu_name`: string, 선택
- `skip`: number, 기본 `0`
- `limit`: number, 기본 `100`, 최대 `1000`

Response `200`: `PaginatedResponse<OptionGroupResponse>`

프런트 역할:

- 메뉴별 옵션 목록 조회
- 보통은 `GET /menus/{menu_name}`의 `option_groups`로 충분하다

### GET `/api/v1/option-groups/{group_name}`

옵션 그룹 단건을 조회한다.

인증: 없음

Path:

- `group_name`: 옵션 그룹명

Query:

- `menu_name`: string, 선택

Response `200`: `OptionGroupResponse`

주요 에러:

- `404 OPTION_GROUP_NOT_FOUND`

### POST `/api/v1/option-groups`

옵션 그룹을 생성하거나 갱신한다. Body의 `menu_name`이 필수다.

인증: 관리자 Basic Auth

Request Body:

```json
{
  "menu_name": "아이스 아메리카노",
  "name": "사이즈",
  "group_order": 0,
  "is_required": true,
  "min_select": 1,
  "max_select": 1,
  "items": [
    {
      "name": "Regular",
      "extra_price": 0,
      "is_default": true,
      "is_available": true,
      "option_order": 0
    },
    {
      "name": "Large",
      "extra_price": 500,
      "is_default": false,
      "is_available": true,
      "option_order": 1
    }
  ]
}
```

Response `201`: `OptionGroupResponse`

주요 에러:

- `400 MENU_NAME_REQUIRED`
- `404 MENU_NOT_FOUND`

### POST `/api/v1/menus/{menu_name}/option-groups`

특정 메뉴에 옵션 그룹을 생성하거나 갱신한다. Path의 `menu_name`을 기준으로 저장한다.

인증: 관리자 Basic Auth

Path:

- `menu_name`: 메뉴명

Request Body:

```json
{
  "name": "당도",
  "group_order": 1,
  "is_required": true,
  "min_select": 1,
  "max_select": 1,
  "items": [
    {
      "name": "기본",
      "extra_price": 0,
      "is_default": true,
      "is_available": true,
      "option_order": 0
    }
  ]
}
```

Response `201`: `OptionGroupResponse`

주요 에러:

- `404 MENU_NOT_FOUND`
- `500 OPTION_GROUP_UPSERT_FAILED`

## 7. Cart API

세션별 장바구니 조회, 전체 교체, 비우기 API. 현재 구현은 항목 단위 추가/삭제가 아니라 장바구니 전체 상태를 `PUT`으로 교체하는 방식이다.

### GET `/api/v1/carts/{session_uuid}`

세션의 장바구니를 조회한다.

인증: 없음

Response `200`:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "status": "active",
  "item_count": 1,
  "total_quantity": 2,
  "total_price": 10000,
  "contains_recommendation_item": false,
  "items": [
    {
      "line_id": "cart-line-id",
      "menu_id": 1,
      "menu_name": "아이스 아메리카노",
      "quantity": 2,
      "unit_price": 4500,
      "line_total": 10000,
      "from_recommendation": false,
      "options": [
        {
          "option_item_id": 2,
          "option_name": "Large",
          "extra_price": 500
        }
      ]
    }
  ],
  "created_at": "2026-04-29T04:00:00Z",
  "updated_at": "2026-04-29T04:01:00Z"
}
```

프런트 역할:

- 장바구니 화면 렌더링
- 음성 주문 action 처리 후 서버 상태 재조회

### PUT `/api/v1/carts/{session_uuid}`

세션의 장바구니를 요청 Body의 items로 전체 교체한다.

인증: 없음

Request Body:

```json
{
  "items": [
    {
      "menu_name": "아이스 아메리카노",
      "quantity": 2,
      "from_recommendation": false,
      "selected_options": [
        {
          "option_item_id": 2
        }
      ]
    }
  ]
}
```

필드:

- `items`: 장바구니 항목 배열
- `items[].menu_name`: 메뉴명
- `items[].quantity`: 1~99
- `items[].from_recommendation`: 추천에서 담았는지 여부
- `items[].selected_options[].option_item_id`: 선택 옵션 항목 ID

Response `200`: `CartResponse`

프런트 역할:

- 메뉴 추가, 수량 변경, 옵션 변경, 삭제 후 현재 장바구니 전체를 서버에 반영

### DELETE `/api/v1/carts/{session_uuid}`

장바구니를 비운다.

인증: 없음

Response `200`: 비워진 `CartResponse`

프런트 역할:

- 주문 취소, 세션 종료, 장바구니 비우기 버튼

## 8. Order API

주문 생성과 주문 조회 API.

### POST `/api/v1/orders`

주문을 생성한다. `items`를 생략하면 서버에 저장된 현재 장바구니 기준으로 주문을 생성한다.

인증: 없음

Request Body:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "items": [
    {
      "menu_name": "아이스 아메리카노",
      "quantity": 2,
      "unit_price": 4500,
      "from_recommendation": false,
      "selected_options": [
        {
          "option_item_id": 2
        }
      ]
    }
  ],
  "used_recommendation": false
}
```

장바구니 기준 주문 생성:

```json
{
  "session_uuid": "32자리_세션_UUID"
}
```

필드:

- `session_uuid`: 필수, 32자
- `items`: 선택, 생략 시 서버 장바구니 사용
- `items[].unit_price`: 프런트 계산값을 보낼 수 있지만 서버에서 검증/재계산한다
- `used_recommendation`: 선택, 생략 시 서버가 판단 가능

Response `201`:

```json
{
  "order_uuid": "주문_UUID",
  "session_uuid": "32자리_세션_UUID",
  "created_at": "2026-04-29T04:05:00Z",
  "total_price": 10000,
  "used_recommendation": false,
  "status": "pending",
  "items": [
    {
      "id": 1,
      "menu_name": "아이스 아메리카노",
      "quantity": 2,
      "unit_price": 4500,
      "from_recommendation": false,
      "options": [
        {
          "option_name": "Large",
          "extra_price": 500
        }
      ]
    }
  ]
}
```

프런트 역할:

- 결제 직전/결제 완료 시 주문 생성
- 성공 후 `order_uuid`로 완료 화면 표시

### GET `/api/v1/orders/{order_uuid}`

주문 단건을 조회한다.

인증: 없음

Response `200`: `OrderResponse`

주요 에러:

- `404 ORDER_NOT_FOUND`

프런트 역할:

- 주문 완료 화면 재진입
- 주문 결과 확인

## 9. Analytics API

관리자 통계 API. 기간과 키오스크 필터를 지원한다.

공통 인증: 관리자 Basic Auth

공통 Query:

- `start_date`: ISO datetime, 선택, 포함
- `end_date`: ISO datetime, 선택, 미포함
- `kiosk_id`: number, 선택

예:

```text
GET /api/v1/analytics/orders?start_date=2026-04-01T00:00:00Z&end_date=2026-05-01T00:00:00Z&kiosk_id=1
```

### GET `/api/v1/analytics/sessions`

세션 통계를 조회한다.

Response `200`:

```json
{
  "total_sessions": 100,
  "simple_mode_sessions": 25,
  "simple_mode_rate": 0.25,
  "help_triggered_count": 3
}
```

### GET `/api/v1/analytics/recommendations`

추천 노출/클릭/주문 전환 통계를 조회한다.

Response `200`:

```json
{
  "total_shown": 100,
  "total_clicked": 20,
  "click_through_rate": 0.2,
  "led_to_order_count": 10,
  "order_conversion_rate": 0.1
}
```

### GET `/api/v1/analytics/orders`

주문/매출 통계를 조회한다.

Response `200`:

```json
{
  "total_orders": 50,
  "total_revenue": 250000,
  "avg_order_price": 5000.0,
  "recommendation_used_count": 12,
  "recommendation_used_rate": 0.24
}
```

## 10. Logs API

프런트 사용자의 화면/행동 로그를 배치로 저장한다.

### POST `/api/v1/logs/batch`

세션 활동 로그를 여러 개 저장한다.

인증: 없음

Request Body:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "events": [
    {
      "seq": 1,
      "occurred_at": "2026-04-29T04:00:00Z",
      "event_type": "click",
      "screen_name": "menu",
      "action_name": "select_menu",
      "target_type": "menu",
      "target_id": "1",
      "target_label": "아이스 아메리카노",
      "duration_ms": 1200,
      "source": "ui",
      "payload_json": {
        "category": "커피"
      }
    }
  ]
}
```

필드:

- `seq`: number, 1 이상, 세션 내 이벤트 순서
- `occurred_at`: ISO datetime
- `event_type`: string, 최대 30자
- `screen_name`: string 또는 null, 최대 30자
- `action_name`: string, 최대 50자
- `target_type`: string 또는 null
- `target_id`: string 또는 null
- `target_label`: string 또는 null
- `duration_ms`: number 또는 null
- `source`: string, 기본 `ui`
- `payload_json`: object 또는 null

Response `201`:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "inserted_count": 1
}
```

주요 에러:

- `404 SESSION_NOT_FOUND`

프런트 역할:

- 사용자 행동 분석
- 추천 클릭률, 화면 체류 시간, 도움 요청 흐름 분석의 원천 데이터

## 11. Face API

얼굴 프레임 분석으로 연령대/성별을 추정하고 세션의 간편모드 여부를 업데이트한다.

### POST `/api/v1/face/analyze`

Base64 JPEG 프레임 목록을 분석한다.

인증: 없음

Request Body:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "frames": [
    "base64_encoded_jpeg_string"
  ]
}
```

필드:

- `session_uuid`: 필수, 32자
- `frames`: Base64 인코딩된 JPEG 문자열 배열, 최소 1개

Response `200`:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "age_group": "60+",
  "gender": "F",
  "age_est": 67,
  "confidence": 0.82,
  "should_use_simple_mode": true,
  "analyzed_at": "2026-04-29T04:00:00Z"
}
```

동작:

- 세션 존재 여부 확인
- 얼굴 분석 수행
- `confidence >= 0.7`이고 고령층 연령대에 해당하면 `should_use_simple_mode=true`
- `vision_event` 저장
- 세션의 `estimated_age_group`, `estimated_gender`, `is_simple_mode` 업데이트

주요 에러:

- `404 SESSION_NOT_FOUND`

프런트 역할:

- 카메라 분석 후 간편모드 UI 자동 전환
- 분석 결과를 세션 상태와 동기화

주의:

- 프레임 문자열은 Data URL prefix가 아니라 순수 Base64로 보내는 방식을 권장한다.
- 카메라 사용 권한 실패 시 이 API를 건너뛰고 일반 모드로 진행할 수 있다.

## 12. Voice API

음성 주문 대화 시작, 메시지 처리, 대화 이력, TTS, 종료 API.

### POST `/api/v1/voice/start`

세션의 음성 주문 attempt를 시작한다. 이미 진행 중인 attempt가 있으면 새로 만들지 않고 기존 attempt의 인사말을 재사용한다.

인증: 없음

Request Body:

```json
{
  "session_uuid": "32자리_세션_UUID"
}
```

Response `200`:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "persona": "elderly",
  "current_stage": "greeting",
  "attempt_started_at": "2026-04-29T04:00:00Z",
  "greeting": {
    "intent": "greet",
    "response_text": "안녕하세요...",
    "next_stage": "greeting",
    "actions": [
      {
        "type": "speak",
        "text": "안녕하세요..."
      }
    ],
    "requires_user_input": true,
    "end_conversation": false
  },
  "audio_b64": "base64_wav_or_null"
}
```

프런트 역할:

- 음성 주문 화면 진입 시 호출
- `audio_b64`가 있으면 재생하고, 없으면 브라우저 `speechSynthesis` fallback 사용

### POST `/api/v1/voice/messages`

사용자 발화를 보내고 AI 응답 및 UI action을 받는다.

인증: 없음

Request Body:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "content": "아이스 아메리카노 두 잔 주세요",
  "selected_category": "커피",
  "selected_menu_name": "아이스 아메리카노"
}
```

필드:

- `session_uuid`: 필수
- `content`: 사용자 발화 텍스트
- `selected_category`: 현재 UI에서 선택된 카테고리, 선택
- `selected_menu_name`: 현재 UI에서 선택된 메뉴명, 선택

Response `200`:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "persona": "general",
  "current_stage": "menu_select",
  "matched_by": "pattern",
  "response": {
    "intent": "order_menu",
    "response_text": "아이스 아메리카노 두 잔을 장바구니에 담을게요.",
    "next_stage": "cart_review",
    "actions": [
      {
        "type": "cart_add",
        "menu_name": "아이스 아메리카노",
        "quantity": 2,
        "option_item_ids": []
      },
      {
        "type": "speak",
        "text": "아이스 아메리카노 두 잔을 장바구니에 담을게요."
      }
    ],
    "requires_user_input": true,
    "end_conversation": false
  },
  "audio_b64": "base64_wav_or_null"
}
```

지원 action:

```text
speak
navigate
scroll
cart_add
option_preview
cart_remove
cart_update
place_order
end_conversation
```

Action별 payload:

```json
{ "type": "speak", "text": "..." }
```

```json
{ "type": "navigate", "target": "menu_list", "category_name": "커피", "menu_name": null }
```

```json
{ "type": "scroll", "direction": "down" }
```

```json
{ "type": "cart_add", "menu_name": "아이스 아메리카노", "quantity": 1, "option_item_ids": [2] }
```

```json
{ "type": "option_preview", "menu_name": "아이스 아메리카노", "option_item_ids": [2] }
```

```json
{ "type": "cart_remove", "menu_name": "아이스 아메리카노", "cart_line_id": "line-id", "option_item_ids": [2] }
```

```json
{ "type": "cart_update", "menu_name": "아이스 아메리카노", "quantity": 2, "cart_line_id": "line-id", "option_item_ids": [2] }
```

```json
{ "type": "place_order" }
```

```json
{ "type": "end_conversation" }
```

프런트 역할:

- STT 결과 텍스트를 서버로 전달
- 응답의 `actions`를 순서대로 처리
- 장바구니 변경 action은 프런트 상태에 반영한 뒤 `PUT /carts/{session_uuid}`로 서버 장바구니와 동기화하는 흐름을 권장

### GET `/api/v1/voice/messages`

현재 음성 주문 attempt의 메시지 이력을 조회한다.

인증: 없음

Query:

- `session_uuid`: string, 필수
- `skip`: number, 기본 `0`
- `limit`: number, 기본 `100`, 최대 `500`

Response `200`:

```json
{
  "items": [
    {
      "id": 1,
      "role": "assistant",
      "content": "안녕하세요...",
      "intent": "greet",
      "matched_by": "cached",
      "created_at": "2026-04-29T04:00:00Z"
    }
  ],
  "total": 1,
  "skip": 0,
  "limit": 100
}
```

프런트 역할:

- 음성 대화 로그 UI
- 새로고침 후 대화 복원

### POST `/api/v1/voice/tts`

텍스트를 WAV 오디오로 변환한다.

인증: 없음

Request Body:

```json
{
  "text": "안녕하세요. 무엇을 주문하시겠어요?"
}
```

Response `200`:

```text
Content-Type: audio/wav
Body: WAV binary
```

주요 에러:

- `404 TTS_UNAVAILABLE`: 서버 TTS 사용 불가

프런트 역할:

- 서버 TTS가 필요할 때 직접 호출
- 실패 시 브라우저 TTS fallback

### POST `/api/v1/voice/end`

진행 중인 음성 주문 attempt를 종료한다.

인증: 없음

Request Body:

```json
{
  "session_uuid": "32자리_세션_UUID"
}
```

Response `200`:

```json
{
  "session_uuid": "32자리_세션_UUID",
  "ended": true
}
```

프런트 역할:

- 음성 주문 화면 종료
- 주문 완료/취소 시 음성 상태 초기화

## 13. Recommendation API

상황 기반 추천과 장바구니 기반 통합 추천 API.

### GET `/api/v1/recommendations/situation`

성별, 나이 또는 연령대를 기준으로 현재 시간대 상황 추천을 반환한다.

인증: 없음

Query:

- `gender`: string, 필수, `M` 또는 `F`
- `age`: number, 선택, 15~100
- `age_group`: string, 선택, 예: `20~29`, `30~39`, `40~49`, `50+`
- `top_n`: number, 기본 `5`, 1~10

주의:

- `age` 또는 `age_group` 중 하나는 반드시 필요하다.
- `age`가 있으면 `age_group`보다 우선 사용된다.

예:

```text
GET /api/v1/recommendations/situation?gender=F&age=67&top_n=5
```

Response `200`:

```json
{
  "mode": "A",
  "situation": "F_60+_14",
  "recommendations": [
    {
      "rank": 1,
      "menu_id": 1,
      "menu_name": "아이스 아메리카노",
      "count": 10,
      "popularity": 0.8,
      "trend_weight": 1.1,
      "final_score": 0.88,
      "copurchase_count": null,
      "strength": null,
      "frequency": null,
      "reasoning": "현재 상황에서 많이 선택된 메뉴입니다."
    }
  ],
  "total_orders": 100,
  "total_items": 200,
  "cache_hit": true
}
```

주요 에러:

- `400`: gender, age, age_group 검증 실패
- `503`: 추천 엔진 미초기화
- `500`: 추천 엔진 내부 오류

프런트 역할:

- 얼굴 분석 후 성별/나이를 기반으로 첫 추천 영역 구성
- 장바구니가 비어 있을 때 추천 메뉴 표시

### POST `/api/v1/recommendations/suggest`

사용자 프로필과 현재 장바구니 메뉴 ID를 기준으로 통합 추천을 반환한다.

인증: 없음

Request Body:

```json
{
  "gender": "M",
  "age": 35,
  "cart_items": [3, 10],
  "top_n": 5,
  "include_trend": true
}
```

필드:

- `gender`: `M | F`
- `age`: number, 15~100
- `cart_items`: menu ID 배열
- `top_n`: number, 기본 `5`, 1~10
- `include_trend`: boolean, 기본 `true`

Response `200`:

```json
{
  "mode": "CF",
  "user_context": {
    "gender": "M",
    "age": 35
  },
  "cart_items": [
    {
      "menu_id": 3,
      "menu_name": "카페라떼"
    }
  ],
  "recommendations": [
    {
      "rank": 1,
      "menu_id": 8,
      "menu_name": "초코 머핀",
      "cf_breakdown": {
        "profile_popularity": 0.6,
        "global_popularity": 0.5,
        "base_score": 0.55,
        "cart_cf_score": 0.7,
        "cf_score": 0.65,
        "cart_support_count": 12,
        "cart_support_ratio": 0.2
      },
      "trend_score": 1.05,
      "final_score": 0.68,
      "reasoning": "현재 장바구니와 함께 자주 주문된 메뉴입니다."
    }
  ],
  "cache_hit": true
}
```

주요 에러:

- `400`: gender 검증 실패 또는 추천 요청 검증 실패
- `404`: 해당 프로필 데이터 없음
- `503`: 추천 엔진 미초기화
- `500`: 추천 엔진 내부 오류

프런트 역할:

- 장바구니에 메뉴가 담긴 이후 함께 살 만한 메뉴 추천
- 결제 직전 추가 추천 영역

## 14. 프런트 권장 호출 흐름

### 기본 주문 흐름

1. 앱 시작 시 `GET /api/v1/kiosks/me`로 단말 API Key 확인
2. 주문 시작 시 `POST /api/v1/sessions` 호출
3. 카메라 사용 가능 시 `POST /api/v1/face/analyze` 호출
4. `GET /api/v1/categories`, `GET /api/v1/menus`로 메뉴 UI 구성
5. 메뉴 상세 진입 시 `GET /api/v1/menus/{menu_name}` 호출
6. 장바구니 변경 시 `PUT /api/v1/carts/{session_uuid}` 호출
7. 결제/주문 확정 시 `POST /api/v1/orders` 호출
8. 완료 후 `PATCH /api/v1/sessions/{session_uuid}`로 `status=ended`, `end_reason=completed`

### 음성 주문 흐름

1. 일반 주문 흐름과 동일하게 세션 생성
2. 음성 화면 진입 시 `POST /api/v1/voice/start`
3. STT 결과마다 `POST /api/v1/voice/messages`
4. 응답 `actions`를 프런트 상태에 반영
5. 장바구니 변경 action 처리 후 `PUT /api/v1/carts/{session_uuid}`
6. `place_order` action 수신 시 `POST /api/v1/orders`
7. 종료 시 `POST /api/v1/voice/end`

### 추천 흐름

1. 얼굴 분석 결과 또는 사용자가 선택한 프로필로 `GET /api/v1/recommendations/situation`
2. 장바구니에 메뉴가 있으면 `POST /api/v1/recommendations/suggest`
3. 추천 메뉴를 장바구니에 넣을 때 `from_recommendation=true`
4. 주문 생성 시 `used_recommendation=true` 또는 생략 후 서버 판단

## 15. 전체 API 빠른 표

| Method | URL | 인증 | 역할 |
|---|---|---|---|
| GET | `/` | 없음 | 서버 루트 상태 |
| GET | `/health` | 없음 | 헬스 체크 |
| POST | `/api/v1/kiosks` | Basic Auth | 키오스크 등록/API Key 발급 |
| GET | `/api/v1/kiosks` | Basic Auth | 키오스크 목록 |
| GET | `/api/v1/kiosks/me` | X-API-Key | 현재 키오스크 조회 |
| POST | `/api/v1/sessions` | X-API-Key | 세션 생성 |
| GET | `/api/v1/sessions` | Basic Auth | 세션 목록 |
| GET | `/api/v1/sessions/{session_uuid}` | 없음 | 세션 단건 조회 |
| PATCH | `/api/v1/sessions/{session_uuid}` | 없음 | 세션 상태 업데이트 |
| GET | `/api/v1/categories` | 없음 | 카테고리 목록 |
| GET | `/api/v1/menus` | 없음 | 메뉴 목록 |
| POST | `/api/v1/menus` | Basic Auth | 메뉴 생성 |
| GET | `/api/v1/menus/{menu_name}` | 없음 | 메뉴 상세/옵션 조회 |
| GET | `/api/v1/option-groups` | 없음 | 옵션 그룹 목록 |
| GET | `/api/v1/option-groups/{group_name}` | 없음 | 옵션 그룹 단건 |
| POST | `/api/v1/option-groups` | Basic Auth | 옵션 그룹 upsert |
| POST | `/api/v1/menus/{menu_name}/option-groups` | Basic Auth | 메뉴별 옵션 그룹 upsert |
| GET | `/api/v1/carts/{session_uuid}` | 없음 | 장바구니 조회 |
| PUT | `/api/v1/carts/{session_uuid}` | 없음 | 장바구니 전체 교체 |
| DELETE | `/api/v1/carts/{session_uuid}` | 없음 | 장바구니 비우기 |
| POST | `/api/v1/orders` | 없음 | 주문 생성 |
| GET | `/api/v1/orders/{order_uuid}` | 없음 | 주문 조회 |
| GET | `/api/v1/analytics/sessions` | Basic Auth | 세션 통계 |
| GET | `/api/v1/analytics/recommendations` | Basic Auth | 추천 통계 |
| GET | `/api/v1/analytics/orders` | Basic Auth | 주문 통계 |
| POST | `/api/v1/logs/batch` | 없음 | 활동 로그 저장 |
| POST | `/api/v1/face/analyze` | 없음 | 얼굴 분석/간편모드 판단 |
| POST | `/api/v1/voice/start` | 없음 | 음성 주문 시작 |
| POST | `/api/v1/voice/messages` | 없음 | 음성 메시지 처리 |
| GET | `/api/v1/voice/messages` | 없음 | 음성 메시지 이력 |
| POST | `/api/v1/voice/tts` | 없음 | TTS WAV 생성 |
| POST | `/api/v1/voice/end` | 없음 | 음성 주문 종료 |
| GET | `/api/v1/recommendations/situation` | 없음 | 상황 기반 추천 |
| POST | `/api/v1/recommendations/suggest` | 없음 | 장바구니 기반 통합 추천 |

## 16. 현재 라우터 등록 참고

`backend/api/v1/router.py`에 실제 등록된 라우터:

- `kiosk`
- `session`
- `menu`
- `option`
- `cart`
- `order`
- `analytics`
- `logs`
- `face`
- `voice`
- `recommendation`

`backend/api/v1/endpoints/vision.py` 파일은 존재하지만 현재 `v1_router`에 include되어 있지 않으므로 프런트 기준 사용 API에서 제외한다.
