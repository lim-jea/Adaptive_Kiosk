# 수정 사항
service/face_service.py

backend/dockerfile

requirments.txt

data/(가중치파일).pth

uv.lock 삭제

환경에 따라 30~60분 정도 패키지 설치시간 소요


# Adaptive Kiosk

디지털 취약계층(고령층 등)이 키오스크를 더 쉽게 사용할 수 있도록 돕는 **지능형 음료 주문 키오스크 시스템**.

카메라로 사용자를 인식하여 UI를 자동으로 간소화하고, 음성 주문, 개인화 추천, 행동 로깅까지 지원하는 React + FastAPI 기반 풀스택 프로젝트.

---

## 프로젝트 구조

```
Adaptive_Kiosk/
├── backend/        # FastAPI 백엔드 (REST API + 음성/추천 파이프라인)
├── frontend/       # React 키오스크 프런트엔드 (Vite)
├── create_data/    # 추천 시스템 학습용 합성 데이터셋 생성 스크립트
└── docs/           # 프로젝트 문서
```

| 구성 요소 | 기술 스택 |
|-----------|----------|
| 백엔드 | FastAPI, SQLAlchemy 2.0 (async), aiomysql, Pydantic v2, uv |
| 프런트엔드 | React 18, Vite, TailwindCSS, axios, react-router |
| DB | MySQL (Aiven Cloud / 로컬) |
| 인증 | HTTP Basic Auth (관리자) + X-API-Key (키오스크 기기) |
| 음성 | Web Speech API (STT) + Google Gemini TTS (옵션) / 브라우저 TTS 폴백 |
| AI | Google Gemini Flash (음성 주문 NLU), Naver DataLab (트렌드, 옵션) |

---

## 핵심 기능

| 분류 | 기능 | 상태 |
|------|------|------|
| 주문 | 메뉴 조회 / 옵션 선택 / 장바구니 / 결제 / 세션 관리 | 완성 |
| 주문 | 서버 측 장바구니 영속화 (세션 기반) | 완성 |
| 인증 | 멀티 키오스크 (X-API-Key) | 완성 |
| 인식 | 얼굴 분석 → 간편모드 자동 전환 | mock 모드 동작, InsightFace 선택 연동 |
| 음성 | Web STT + 캔드 응답 fast-path + Gemini NLU + TTS | 완성 |
| 추천 | 협업 필터링(CF) 중심 개인화 추천 + 트렌드 반영 | 완성 |
| 로그 | 세션 활동 로그 / 대화 로그 배치 수집 | 완성 |
| 관리 | 분석 / 관리자 API | 완성 |

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
cp .env.example .env                             # 환경변수 파일 복사
# .env 편집 (DB 연결 URL, 관리자 계정 등 — 아래 "환경 변수" 참고)
uv run uvicorn main:app --reload --port 5000
```

서버 시작 시 시드 데이터(카테고리/메뉴/옵션)와 테스트용 키오스크 3대가 자동 생성됩니다.

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

> ⚠️ `.env` 파일에는 실제 값이 들어갑니다. **Git에 커밋하지 마세요.**
> 아래 예시의 `your_*` 자리 표시자는 실제 자격 증명으로 교체해야 합니다.

### `backend/.env`

```env
# 관리자 계정 (Swagger 문서 + 관리자 API)
KIOSK_USERNAME=your_admin_username
KIOSK_PASSWORD=your_admin_password

# DB 연결 URL
# 로컬 MySQL:   mysql+aiomysql://user:password@127.0.0.1:3306/dbname
# Aiven Cloud:  mysql+aiomysql://user:password@host.aivencloud.com:port/defaultdb
# TiDB Cloud:   mysql+aiomysql://user:password@host.tidbcloud.com:4000/test
DATABASE_CONN=

# Google Gemini API (음성 주문 NLU / 선택적 TTS)
GENAI_API_KEY=your_google_genai_api_key
GENAI_TTS_ENABLED=false          # true 시 서버 측 Gemini TTS 사용, false 면 브라우저 TTS 폴백

# Naver DataLab API (선택, 트렌드 기반 추천 보정)
NAVER_TREND_ENABLED=false        # true 시에만 Naver 호출
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
TREND_CACHE_TTL=3600             # 트렌드 캐시 유지 시간(초)
```

> DB 호스트에 `aivencloud` 또는 `tidbcloud`가 포함되면 SSL이 자동 활성화됩니다. 그 외 클라우드에서 SSL이 필요하면 `core/database.py`에서 추가 설정이 필요합니다.

### `frontend/.env`

```env
VITE_API_URL=http://localhost:5000
VITE_KIOSK_API_KEY=              # 백엔드 시작 시 콘솔에 출력된 64자 hex
VITE_ENCRYPTION_ENABLED=false
```

---

## 사용 흐름

```
LandingPage (시작)
   ↓ POST /api/v1/sessions          (X-API-Key 헤더)
CameraPage (얼굴 캡처)
   ↓ POST /api/v1/face/analyze      (mock 또는 InsightFace)
ResultPage (연령/성별/간편모드 결정)
   ↓
KioskPage
   GET  /api/v1/categories
   GET  /api/v1/menus
   GET  /api/v1/menus/{name}        (옵션 그룹 포함)
   GET  /api/v1/recommendations/... (개인화 + 트렌드)
   PUT  /api/v1/carts/{uuid}        (장바구니 영속화)
   음성: POST /api/v1/voice/start → /voice/messages → /voice/end
PaymentPage
   POST /api/v1/orders              (서버가 가격 재검증 + 옵션 스냅샷)
CompletionPage
   PATCH /api/v1/sessions/{uuid}    { status: ended, end_reason: completed }

(모든 화면) POST /api/v1/logs/batch  (세션 활동 로그 배치 업로드)
```

---

## 음성 주문 파이프라인

1. **STT** — 프런트 `useSTT` (Web Speech API, ko-KR, 연속 인식 + 침묵 커밋)
2. **매칭** — 백엔드가 다음 순서로 fast-path 매칭 시도
   - 캔드 시나리오 (`data/canned_responses.json`)
   - 코드 정규식 패턴 (인사/취소/긍정 등)
   - 메뉴 이름 직접 매칭 (alias 포함)
   - 캐시된 장바구니 요약
   - 실패 시 Gemini 호출
3. **TTS** — 인라인 WAV(`audio_b64`)가 있으면 재생, 없으면 브라우저 `speechSynthesis` 폴백
4. **재시도** — Chrome `InvalidStateError` 발생 시 `useSTT.start()`가 최대 3회까지 150ms 간격으로 재시도

---

## 문서

- [docs/프로젝트 전체 정리.md](docs/프로젝트%20전체%20정리.md) — 전체 구조, DB, API, 시나리오
- [backend/docs/백엔드 구조 설명.md](backend/docs/백엔드%20구조%20설명.md) — 백엔드 세부 구조
- [backend/docs/음성 주문 시나리오 테스트 케이스.md](backend/docs/음성%20주문%20시나리오%20테스트%20케이스.md) — 음성 fast-path 케이스
- [backend/docs/추천시스템_현재구조와평가.md](backend/docs/추천시스템_현재구조와평가.md) — 추천 시스템 구조
- [backend/docs/추천시스템_데이터계산검증.md](backend/docs/추천시스템_데이터계산검증.md) — 추천 모델 검증
- [create_data/README.md](create_data/README.md) — 합성 데이터셋 생성 방법

---

## DB 모델 변경 시

DB 컬럼/테이블이 바뀌면 SQLAlchemy `create_all`은 기존 테이블을 변경하지 않으므로 **수동 리셋**이 필요합니다.

```sql
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS
  chat_messages,
  session_activity_logs,
  recommendation_events,
  vision_events,
  order_items,
  orders,
  carts,
  menu_options,
  menus,
  kiosk_sessions,
  kiosks;
SET FOREIGN_KEY_CHECKS=1;
```

서버를 재시작하면 새 스키마로 다시 생성됩니다.

---

## 라이선스 / 출처

본 프로젝트는 26년도 산학협력 캡스톤 과제로 제작되고 있습니다.
