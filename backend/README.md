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
- 시드 데이터(파생 카테고리 8개 / 메뉴 22개 / 메뉴 옵션)가 자동 생성됩니다.
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
| GET | `/api/v1/categories` | 없음 | 메뉴 데이터에서 파생한 카테고리 목록 |
| GET | `/api/v1/menus` | 없음 | 메뉴 목록 (페이지네이션, 카테고리 필터) |
| POST | `/api/v1/menus` | Basic Auth | 메뉴 생성 |
| GET | `/api/v1/menus/{menu_name}` | 없음 | 메뉴 상세 + 옵션 그룹 |

### Option

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| GET | `/api/v1/option-groups` | 없음 | 메뉴별 옵션 그룹 목록 (`menu_name` 필터 가능) |
| GET | `/api/v1/option-groups/{group_name}` | 없음 | 옵션 그룹 단건 (`menu_name` 쿼리 가능) |
| POST | `/api/v1/option-groups` | Basic Auth | 특정 메뉴의 옵션 그룹 upsert (`menu_name` 필수) |
| POST | `/api/v1/menus/{menu_name}/option-groups` | Basic Auth | 특정 메뉴의 옵션 그룹 upsert |

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

### Recommendation / Voice

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| GET | `/api/v1/recommendations/situation` | 없음 | 상황 기반 추천 |
| POST | `/api/v1/recommendations/suggest` | 없음 | 통합 추천 |
| POST | `/api/v1/voice/start` | 없음 | 음성 주문 시도 시작 |
| POST | `/api/v1/voice/messages` | 없음 | 음성 주문 발화 처리 |
| GET | `/api/v1/voice/messages` | 없음 | 음성 메시지 이력 조회 |
| POST | `/api/v1/voice/tts` | 없음 | TTS WAV 반환 |
| POST | `/api/v1/voice/end` | 없음 | 음성 주문 시도 종료 |

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
├── model.py                      # SQLAlchemy ORM 통합 정의
├── schemas.py                    # Pydantic 요청/응답 통합 정의
│
├── crud/                         # 순수 DB CRUD
├── services/                     # 비즈니스 로직 (가격 검증, 통계 집계, 얼굴 분석 등)
│
├── api/v1/
│   ├── router.py                 # v1 라우터 등록
│   └── endpoints/
│       ├── kiosk.py
│       ├── session.py
│       ├── menu.py
│       ├── option.py
│       ├── order.py
│       ├── face.py
│       ├── analytics.py
│       ├── recommendation.py
│       └── voice.py
│
├── data/
│   ├── canned_responses.json     # 음성 주문 시나리오 / 템플릿 / 조각 매뉴얼
│   └── tts_cache/                # Gemini TTS WAV 영구 캐시 (gitignore)
│
├── scripts/
│   ├── seed_menu.py              # 메뉴/menu_options 초기 데이터 + 레거시 마이그레이션
│   ├── seed_sample.py            # 테스트용 키오스크 3대 + 샘플 주문
│   └── prewarm_tts.py            # 음성 조각/시나리오 일괄 합성 + 캐시 관리
│
└── docs/
    ├── 백엔드 구조 설명.md
    └── 프로젝트 전체 정리.md
```

---

## 음성 주문 TTS 캐시 관리

음성 주문 응답은 같은 Gemini 클라이언트에서 **2.5 Flash TTS**로 합성됩니다. 매 요청마다 합성하면 느리고 비싸기 때문에 자주 쓰이는 문구를 미리 합성해 **`backend/data/tts_cache/{sha256}.wav`**에 영구 저장하고, 런타임에서는 디스크 캐시 → 라이브 합성 순으로 조회합니다.

### 캐시 대상

[`data/canned_responses.json`](data/canned_responses.json) 파일이 합성 대상의 단일 출처입니다.

| 섹션 | 설명 |
|---|---|
| `scenarios` | stage + 정규식으로 매칭되는 즉시 응답 (인사/취소/긍정/카테고리 선택 등). `response_text`를 그대로 합성. |
| `templates` | `{menu}`, `{option}` 슬롯을 가진 문장. DB의 메뉴/옵션을 읽어 모든 조합으로 확장. |
| `fragments` | 단어 단위 조각(메뉴 이름, 옵션 이름, 한국어 숫자, 연결구). 런타임에 PCM을 이어붙여 임의 조합 응답 생성. |

`fragments`에는 한국어 숫자(`일`~`구`, `십`/`백`/`천`/`만`/`십만`/`백만`)가 포함되어 있어 가격 안내(`총 사천오백원입니다.`) 같은 동적 응답도 Gemini TTS 호출 없이 조각 합성으로 만들 수 있습니다.

### `scripts/prewarm_tts.py` 사용법

> ⚠️ **반드시 가상환경에서 실행하세요.** 시스템 Python으로 실행하면 `ModuleNotFoundError: sqlalchemy` 가 납니다.

```bash
# uv 사용 (권장 — 활성화 필요 없음)
uv run python -m scripts.prewarm_tts

# 또는 가상환경 활성화 후
.venv\Scripts\Activate.ps1   # PowerShell
python -m scripts.prewarm_tts
```

| 명령 | 동작 |
|---|---|
| `python -m scripts.prewarm_tts` | 디스크 캐시에 없는 항목만 합성. 두 번째 실행부터는 거의 즉시 끝남. |
| `python -m scripts.prewarm_tts --list` | 합성 대상 텍스트만 출력. `[✓]`는 캐시 hit, `[ ]`는 합성 필요. |
| `python -m scripts.prewarm_tts --force` | 이미 캐시된 항목까지 전부 다시 합성 (음성/모델 변경 시). |
| `python -m scripts.prewarm_tts --clean` | `data/tts_cache/` 통째로 삭제. 시연/테스트 후 정리용. |

### 권장 시연 흐름

```bash
# 1. 시연 전 한 번
uv run python -m scripts.prewarm_tts --list   # 어떤 게 새로 만들어질지 확인
uv run python -m scripts.prewarm_tts          # 약 60-80개 음성 합성, 1-3분 소요

# 2. 시연 동안은 서버가 디스크 캐시 hit으로 즉시 응답
uv run uvicorn main:app --reload

# 3. 시연 종료 후 정리
uv run python -m scripts.prewarm_tts --clean
```

### 시나리오 / 조각 추가

`data/canned_responses.json` 편집 후 다음 prewarm 실행 시 자동으로 디스크에 추가됩니다.

- **새 정형 응답**: `scenarios` 배열에 항목 추가 (id, match, response). `response_text`는 변경 시 sha256이 바뀌어 새로 합성됩니다.
- **새 템플릿**: `templates` 배열에 `{ "id": "...", "expand": "menus|options", "text": "{menu} ..." }` 추가.
- **새 조각**: `fragments.static` 배열에 짧은 문자열 추가. 런타임 조합용.

### 동작 우선순위 (런타임)

```
사용자 발화
  ↓
[1] match_canned (시나리오 정규식)         → 디스크 캐시 hit, ~5ms
  ↓ miss
[2] match_pattern (코드 패턴)              → 즉시
  ↓ miss
[3] match_menu_name (메뉴 이름 직접 언급)  → 즉시
  ↓ miss
[4] Gemini chat (시나리오/템플릿/조각 매뉴얼 주입)
     ↓ AI 응답
   audio_segments 있음? → compose_audio_from_segments (조각 PCM concat) → 즉시
   없음?               → synthesize_speech(text) → 디스크 hit 또는 Gemini TTS 호출
```

---

## DB 모델 변경 시

SQLAlchemy의 `Base.metadata.create_all`은 **이미 존재하는 테이블을 변경하지 않습니다.** 모델을 수정한 경우 현재 구조 기준으로 필요한 테이블을 삭제하고 재생성해야 합니다.

```sql
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS kiosk_sessions, kiosks, menu_options, menus,
                     order_item_options, order_items,
                     orders, recommendation_events, vision_events, chat_messages;
SET FOREIGN_KEY_CHECKS=1;
```

서버를 재시작하면 새 스키마로 테이블이 만들어지고 시드 데이터가 자동 삽입됩니다.

---

## 자세한 문서

- [백엔드 구조 설명](docs/백엔드%20구조%20설명.md)
- [프로젝트 전체 정리](docs/프로젝트%20전체%20정리.md)
