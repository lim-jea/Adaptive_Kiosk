# Adaptive Kiosk

카메라 기반 사용자 인식 + 음성 주문 + 음료 추천을 결합한 지능형 키오스크 시스템의 백엔드 서버.

## 프로젝트 개요

디지털 환경에 익숙하지 않거나 키오스크 사용에 어려움을 겪는 사용자를 보조하는 지능형 키오스크 시스템이다.

### 핵심 기능

- **비전 기반 UI 자동 전환**: 카메라로 사용자를 인식하여, 고령층으로 판단되면 큰 버튼/큰 글씨의 간편 모드로 자동 전환
- **음성 주문**: 디지털 취약계층에게 TTS로 안내하고, 음성(STT)으로 주문을 받아 AI가 처리
- **음료 추천**: 선호 카테고리 기반 추천 + 협업 필터링 기반 다른 계열 발견형 추천
- **비사용자 프라이버시 보호**: 주 사용자 외 얼굴/사람 영역 블러 처리
- **로그 기반 정량 평가**: 모든 상호작용을 기록하여 접근성 향상 효과를 수치로 측정
- **멀티 키오스크**: 서버 1대로 여러 키오스크를 관리, 키오스크별 API 키 인증

## 기술 스택

| 분류 | 기술 |
|------|------|
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) |
| DB | MySQL (aiomysql) |
| Auth | JWT (PyJWT) + HTTP Basic Auth (Swagger) + API Key (키오스크) |
| AI | Google Gemini Flash Lite (음성 주문 시나리오 처리) |
| 패키지 관리 | uv |

## 시작하기

### 1. 의존성 설치

```bash
uv sync
```

### 2. 환경변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```env
KIOSK_USERNAME=   # Swagger 문서 접근 계정
KIOSK_PASSWORD=   # Swagger 문서 접근 비밀번호

DATABASE_CONN=   # 
user:pass@host:port/dbname

JWT_SECRET_KEY=  # JWT 시크릿 키
JWT_ALGORITHM=HS256

GENAI_API_KEY=   # Google Gemini API 키 (음성 주문용)
```

### 3. DB 생성

MySQL에서 데이터베이스 생성:



테이블은 서버 시작 시 자동 생성됩니다.

### 4. 서버 실행

```bash
uv run uvicorn main:app --reload --port 5000
```

### 5. API 문서 확인

http://localhost:5000/docs 접속 후 `.env`에 설정한 계정으로 로그인.

## API 엔드포인트

### Kiosk (키오스크 관리)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/kiosks/register` | 키오스크 등록 (API 키 발급) |
| POST | `/api/v1/kiosks/login` | 키오스크 로그인 |
| GET | `/api/v1/kiosks` | 전체 키오스크 목록 |
| GET | `/api/v1/kiosks/{id}` | 키오스크 상세 |

### Session (세션)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/sessions` | 세션 시작 (X-API-Key 필수) |
| GET | `/api/v1/sessions/{id}` | 세션 조회 |
| PATCH | `/api/v1/sessions/{id}` | 세션 업데이트 |
| POST | `/api/v1/sessions/{id}/end` | 세션 종료 |

### Vision (비전)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/vision/{session_id}` | 비전 결과 수신 + 간편모드 판단 |

### Voice (음성 주문)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/voice/{session_id}/start` | 음성 주문 시작 (TTS 안내) |
| POST | `/api/v1/voice/process` | STT 결과 처리 (패턴 매칭/Gemini) |
| GET | `/api/v1/voice/{session_id}/history` | 대화 이력 조회 |

### Recommendation (추천)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/recommendations/request` | 추천 요청 |
| POST | `/api/v1/recommendations/click` | 추천 클릭 로그 |

### Order (주문)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/orders` | 주문 생성 |
| GET | `/api/v1/orders/{id}` | 주문 조회 |

### Menu (메뉴)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/menus` | 메뉴 목록 |
| GET | `/api/v1/menus/categories` | 카테고리 목록 |

### Analytics (분석)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/v1/analytics/sessions` | 세션 통계 |
| GET | `/api/v1/analytics/recommendations` | 추천 통계 |
| GET | `/api/v1/analytics/orders` | 주문 통계 |

## 프로젝트 구조

```
Adaptive_Kiosk/
├── main.py              # 앱 진입점
├── core/                # 설정, DB, 보안
├── models/              # ORM 테이블 정의
├── schemas/             # Pydantic 스키마
├── crud/                # DB 접근 로직
├── services/            # 비즈니스 로직
├── api/v1/endpoints/    # API 엔드포인트
└── docs/                # 문서
```

자세한 구조 설명은 [docs/백엔드 구조 설명.md](docs/백엔드%20구조%20설명.md)를 참고.
