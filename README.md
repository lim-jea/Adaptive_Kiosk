# Adaptive Kiosk

디지털 취약계층(고령층 등)이 키오스크를 더 쉽게 사용할 수 있도록 돕는 **지능형 음료 주문 키오스크 시스템**.

카메라로 사용자를 인식하여 UI를 자동으로 간소화하고, 옵션 선택과 주문, 추후 음성 주문 / AI 추천까지 지원하는 React + FastAPI 기반 풀스택 프로젝트.

---

## 프로젝트 구조

```
Adaptive_Kiosk/
├── backend/        # FastAPI 백엔드 (REST API)
├── frontend/       # React 키오스크 프런트엔드 (Vite)
└── docs/           # 프로젝트 문서
```

| 구성 요소 | 기술 스택 |
|-----------|----------|
| 백엔드 | FastAPI, SQLAlchemy 2.0 (async), aiomysql, Pydantic v2, uv |
| 프런트엔드 | React 19, Vite, TailwindCSS, axios |
| DB | MySQL (Aiven Cloud / 로컬) |
| 인증 | HTTP Basic Auth (관리자) + X-API-Key (키오스크 기기) |
| AI (2단계) | Google Gemini Flash Lite (음성 주문), InsightFace (얼굴 분석) |

---

## 핵심 기능

| 단계 | 기능 | 상태 |
|------|------|------|
| 1단계 | 메뉴 조회 / 옵션 선택 / 주문 / 결제 / 세션 관리 | **완성** |
| 1단계 | 멀티 키오스크 (X-API-Key) | **완성** |
| 1단계 | 얼굴 분석 → 간편모드 자동 전환 | mock 모드 동작, InsightFace 미연동 |
| 2단계 | 음료 추천 (행동 기반 + CF) | 구조 완성, 모델 미구현 |
| 2단계 | 음성 주문 (TTS/STT + Gemini) | 구조 완성, 프런트 연동 필요 |
| 3단계 | 분석 / 관리자 대시보드 | 분석 API 완성 |

---

## 빠른 시작

### 사전 요구사항

- Python 3.11+ 와 [uv](https://docs.astral.sh/uv/) (`pip install uv`)
- Node.js 20+
- MySQL 8 (로컬) 또는 클라우드 DB (Aiven, TiDB Cloud 등)

### 1. 백엔드 실행

```bash
cd backend
uv sync                                          # 의존성 설치 (최초 1회)
cp .env.example .env                             # 환경변수 파일 복사 (없다면 직접 작성)
# .env 편집 (DB 연결 URL, 관리자 계정 등)
uv run uvicorn main:app --reload --port 5000
```

서버 시작 시 시드 데이터(15개 카테고리, 22개 메뉴, 6개 옵션 그룹)와 테스트용 키오스크 3대가 자동 생성됩니다.

콘솔에 출력되는 **API 키**를 복사해 두세요:

```
[TEST KIOSK API KEYS — copy one to frontend/.env VITE_KIOSK_API_KEY]
  1층 로비 키오스크: <64자 hex>
  ...
```

API 문서: http://localhost:5000/docs (Basic Auth 로그인 필요)

### 2. 프런트엔드 실행

```bash
cd frontend
npm install
cp .env.example .env
# .env 편집: VITE_KIOSK_API_KEY 에 백엔드에서 받은 키 입력
npm run dev
```

브라우저: http://localhost:5173

---

## 환경 변수

### `backend/.env`

```env
KIOSK_USERNAME=your_admin_username
KIOSK_PASSWORD=your_admin_password

DATABASE_CONN=mysql+aiomysql://your_user:your_password@your_host:your_port/your_db

GENAI_API_KEY=your_google_genai_key
```

> ⚠️ DB가 클라우드(Aiven 등)인 경우 `aivencloud` 또는 `tidbcloud` 호스트가 포함되면 SSL이 자동 활성화됩니다. 그 외 클라우드에서 SSL이 필요한 경우 `core/database.py`에서 추가 설정 필요.

### `frontend/.env`

```env
VITE_API_URL=http://localhost:5000
VITE_KIOSK_API_KEY=your_kiosk_api_key_64_hex
VITE_ENCRYPTION_ENABLED=false
```

---

## 사용 흐름

```
LandingPage (시작)
   ↓ POST /api/v1/sessions  (X-API-Key)
CameraPage (5장 캡처)
   ↓ POST /api/v1/face/analyze  (mock 모드)
ResultPage (연령/성별/간편모드)
   ↓
KioskPage
   GET /api/v1/categories
   GET /api/v1/menus
   GET /api/v1/menus/{name}  (옵션 그룹 포함)
   ↓ 장바구니 추가 (React state)
PaymentPage
   POST /api/v1/orders  (서버가 가격 재검증 + 옵션 스냅샷)
CompletionPage
   PATCH /api/v1/sessions/{uuid}  { status: ended, end_reason: completed }
```

---

## 문서

- [docs/프로젝트 전체 정리.md](docs/프로젝트%20전체%20정리.md) — 전체 구조, DB, API, 시나리오
- [backend/docs/백엔드 구조 설명.md](backend/docs/백엔드%20구조%20설명.md) — 백엔드 세부 구조

---

## DB 모델 변경 시

DB 컬럼/테이블이 바뀌면 SQLAlchemy `create_all`은 기존 테이블을 변경하지 않으므로 **수동 리셋**이 필요합니다.

```sql
-- DB 클라이언트에서:
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS categories, kiosk_sessions, kiosks, menu_option_groups, menus,
                     option_groups, option_items, order_item_options, order_items,
                     orders, recommendation_events, vision_events, voice_conversations;
SET FOREIGN_KEY_CHECKS=1;
```

서버 재시작하면 새 스키마로 다시 생성됩니다.

---

## 라이선스 / 출처

본 프로젝트는 26년도 산학협력 캡스톤 과제로 제작되고 있습니다.
