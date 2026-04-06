# Adaptive Kiosk — Backend

지능형 키오스크 시스템의 FastAPI 백엔드 서버.

> 📘 **전체 프로젝트(프런트+백엔드) 개요는 [루트 README](../README.md)를 먼저 참고하세요.**

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| Framework | FastAPI (전체 async) |
| ORM | SQLAlchemy 2.0 (async) + aiomysql |
| DB | MySQL (로컬 또는 클라우드: Aiven, TiDB Cloud 등) |
| Auth | HTTP Basic Auth (관리자) + X-API-Key (키오스크) |
| AI | Google Gemini Flash Lite (음성 주문, 2단계) / InsightFace (얼굴 분석, 2단계) |
| 패키지 관리 | uv (`pyproject.toml`) |

---

## 시작하기

### 1. 의존성 설치

```bash
uv sync
```

### 2. 환경변수

```bash
cp .env.example .env
```

`.env` 편집:

```env
KIOSK_USERNAME=your_admin_username
KIOSK_PASSWORD=your_admin_password

DATABASE_CONN=mysql+aiomysql://your_user:your_password@your_host:your_port/your_db

GENAI_API_KEY=your_google_genai_api_key
```

`DATABASE_CONN`에 `aivencloud` 또는 `tidbcloud` 호스트가 포함되면 SSL이 자동 활성화됩니다.

### 3. DB 준비

DB 서버에 연결할 수 있는지 확인하고, 빈 데이터베이스를 생성해두면 서버 시작 시 테이블이 자동으로 만들어집니다.

```sql
-- 로컬 MySQL 예시
CREATE DATABASE your_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 4. 서버 실행

```bash
uv run uvicorn main:app --reload --port 5000
```

- API 문서: http://localhost:5000/docs (Basic Auth 로그인 필요)
- 시드 데이터(15 카테고리 / 22 메뉴 / 6 옵션 그룹)와 테스트용 키오스크 3대가 자동 생성됩니다.
- 콘솔에 출력되는 **API 키**를 프런트엔드 `.env`의 `VITE_KIOSK_API_KEY`에 입력하세요.

---

## 인증 구조

| 대상 | 인증 방식 | 처리 위치 |
|------|-----------|----------|
| Swagger 문서 (`/docs`, `/redoc`) | HTTP Basic Auth | `main.py` 미들웨어 |
| 관리자 API (analytics, kiosks 생성/목록) | HTTP Basic Auth | `Depends(verify_credentials)` |
| 세션 시작 (`POST /sessions`) | X-API-Key 헤더 | `Depends(get_current_kiosk)` |
| 그 외 (메뉴, 주문 등) | 인증 없음 | session_uuid로 식별 |

---

## API 엔드포인트

### Kiosk

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/v1/kiosks` | Basic Auth | 키오스크 생성 + API 키 발급 |
| GET | `/api/v1/kiosks` | Basic Auth | 키오스크 목록 (페이지네이션) |
| GET | `/api/v1/kiosks/me` | X-API-Key | 현재 인증된 키오스크 정보 |

### Session

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/v1/sessions` | X-API-Key | 세션 생성 |
| GET | `/api/v1/sessions` | Basic Auth | 세션 목록 |
| GET | `/api/v1/sessions/{session_uuid}` | 없음 | 세션 단건 조회 |
| PATCH | `/api/v1/sessions/{session_uuid}` | 없음 | 세션 상태 갱신 (종료, 간편모드 등) |

### Menu / Category

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| GET | `/api/v1/categories` | 없음 | 카테고리 목록 |
| POST | `/api/v1/categories` | Basic Auth | 카테고리 생성 |
| GET | `/api/v1/menus` | 없음 | 메뉴 목록 (페이지네이션, 카테고리 필터) |
| POST | `/api/v1/menus` | Basic Auth | 메뉴 생성 |
| GET | `/api/v1/menus/{menu_name}` | 없음 | 메뉴 상세 + 옵션 그룹 |

### Option

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| GET | `/api/v1/option-groups` | 없음 | 옵션 그룹 목록 |
| GET | `/api/v1/option-groups/{group_name}` | 없음 | 옵션 그룹 단건 |
| POST | `/api/v1/option-groups` | Basic Auth | 옵션 그룹 upsert |
| POST | `/api/v1/menus/{menu_name}/option-groups` | Basic Auth | 메뉴-옵션 그룹 연결 |

### Order

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/v1/orders` | 없음 | 주문 생성 (서버 가격 재검증) |
| GET | `/api/v1/orders/{order_uuid}` | 없음 | 주문 단건 조회 |

### Face (얼굴 분석)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| POST | `/api/v1/face/analyze` | 없음 | 카메라 프레임 분석 + 간편모드 판단 |

### Analytics (관리자)

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| GET | `/api/v1/analytics/sessions` | Basic Auth | 세션 통계 (기간/키오스크 필터) |
| GET | `/api/v1/analytics/recommendations` | Basic Auth | 추천 통계 |
| GET | `/api/v1/analytics/orders` | Basic Auth | 주문 통계 |

### 비활성 (2단계 활성화 예정)

`api/v1/router.py`에서 주석 해제하면 활성화됩니다.

| 라우터 | 설명 |
|--------|------|
| `recommendation` | 추천 요청/클릭 로그 |
| `voice` | 음성 주문 (TTS/STT + Gemini) |

---

## 디렉토리 구조

```
backend/
├── main.py                       # 앱 진입점, CORS, docs 보호 미들웨어, lifespan
├── pyproject.toml
├── .env                          # 환경변수 (gitignore)
│
├── core/
│   ├── config.py                 # pydantic-settings 기반 환경변수 로드
│   ├── database.py               # async 엔진, 커넥션 풀, SSL, get_db()
│   ├── enums.py                  # SessionStatus, OrderStatus, ServingTemperature 등
│   └── security.py               # HTTP Basic Auth (verify_credentials)
│
├── models/                       # SQLAlchemy ORM
│   ├── kiosk.py
│   ├── session.py                # session_uuid 외부 식별자
│   ├── menu.py                   # categories, menus, option_groups, option_items
│   ├── order.py                  # orders (order_uuid), order_items, order_item_options
│   ├── vision_event.py
│   ├── recommendation_event.py
│   └── voice_conversation.py
│
├── schemas/                      # Pydantic 요청/응답
│   ├── common.py                 # PaginatedResponse, ErrorResponse
│   ├── kiosk.py
│   ├── session.py
│   ├── menu.py
│   ├── option.py
│   ├── order.py
│   ├── face.py
│   ├── analytics.py
│   ├── vision.py
│   ├── recommendation.py
│   └── voice.py
│
├── crud/                         # 순수 DB CRUD
├── services/                     # 비즈니스 로직 (가격 검증, 통계 집계, 얼굴 분석 등)
│
├── api/v1/
│   ├── router.py                 # 라우터 등록 (1단계 활성, 2단계 주석)
│   └── endpoints/
│       ├── kiosk.py
│       ├── session.py
│       ├── menu.py
│       ├── option.py
│       ├── order.py
│       ├── face.py
│       ├── analytics.py
│       ├── vision.py             # (2단계)
│       ├── recommendation.py     # (2단계)
│       └── voice.py              # (2단계)
│
├── scripts/
│   ├── seed_menu.py              # 카테고리/메뉴/옵션 초기 데이터
│   └── seed_sample.py            # 테스트용 키오스크 3대 + 샘플 주문
│
└── docs/
    ├── 백엔드 구조 설명.md
    └── 프로젝트 전체 정리.md
```

---

## DB 모델 변경 시

SQLAlchemy의 `Base.metadata.create_all`은 **이미 존재하는 테이블을 변경하지 않습니다.** 모델을 수정한 경우 모든 테이블을 강제로 삭제하고 재생성해야 합니다.

```sql
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS categories, kiosk_sessions, kiosks, menu_option_groups, menus,
                     option_groups, option_items, order_item_options, order_items,
                     orders, recommendation_events, vision_events, voice_conversations;
SET FOREIGN_KEY_CHECKS=1;
```

서버를 재시작하면 새 스키마로 테이블이 만들어지고 시드 데이터가 자동 삽입됩니다.

---

## 자세한 문서

- [백엔드 구조 설명](docs/백엔드%20구조%20설명.md)
- [프로젝트 전체 정리](docs/프로젝트%20전체%20정리.md)
