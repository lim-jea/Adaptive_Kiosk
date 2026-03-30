# Adaptive Kiosk - 지능형 음료 키오스크 API

카메라 기반 사용자 인식을 통해 키오스크 UI를 자동으로 간소화하고, 음료 추천 및 주문 관리를 제공하는 FastAPI 백엔드 서버.

## 기술 스택

- **Framework**: FastAPI (async)
- **ORM**: SQLAlchemy 2.0 (async)
- **DB**: MySQL (aiomysql)
- **Auth**: JWT (PyJWT) + HTTP Basic Auth (Swagger 보호)
- **패키지 관리**: uv

## 시작하기

### 1. 의존성 설치

```bash
uv sync
```

### 2. 환경변수 설정

`.env` 파일을 프로젝트 루트에 생성:

```env
DOCS_USERNAME="capstone"
DOCS_PASSWORD="capstone123"

DATABASE_CONN="mysql+aiomysql://root:root@127.0.0.1:3306/fastapi_db"

JWT_SECRET_KEY="your-secret-key"
JWT_ALGORITHM="HS256"
```

### 3. DB 생성

MySQL에서 데이터베이스 생성:

```sql
CREATE DATABASE fastapi_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

테이블은 서버 시작 시 자동 생성됩니다.

### 4. 서버 실행

```bash
uv run uvicorn main:app --reload --port 5000
```

### 5. API 문서 확인

`http://localhost:5000/docs` 접속 후 `.env`에 설정한 계정으로 로그인.

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| POST | `/api/v1/sessions` | 세션 시작 |
| GET | `/api/v1/sessions/{id}` | 세션 조회 |
| PATCH | `/api/v1/sessions/{id}` | 세션 업데이트 (간편모드 등) |
| POST | `/api/v1/sessions/{id}/end` | 세션 종료 |
| POST | `/api/v1/vision/{session_id}` | 비전 결과 수신 + 간편모드 판단 |
| POST | `/api/v1/recommendations/request` | 추천 요청 |
| POST | `/api/v1/recommendations/click` | 추천 클릭 로그 |
| POST | `/api/v1/orders` | 주문 생성 |
| GET | `/api/v1/orders/{id}` | 주문 조회 |
| GET | `/api/v1/menus` | 메뉴 목록 |
| GET | `/api/v1/menus/categories` | 카테고리 목록 |
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

자세한 구조 설명은 [docs/백엔드 구조 설명.md](docs/백엔드%20구조%20설명.md)를 참고하세요.
