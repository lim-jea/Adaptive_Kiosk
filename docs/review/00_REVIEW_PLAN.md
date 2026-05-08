# 백엔드 코드 전수 검토 계획

> 작성일: 2026-05-04
> 대상 브랜치: `admin_tab` (main 위에서 분기)
> 검토 목적: 불필요한 코드 제거, 의도와 어긋난 동작 식별, 효율성 개선

---

## 0. 검토 원칙 (반드시 준수)

1. **API 입출력 형식 불변 (Hard Rule)**
   - 프런트엔드가 main 브랜치 기반으로 이미 진행 중이므로,
   - **신규 추가 API가 아닌 한**, 기존 엔드포인트의 **request body / query / response schema는 변경 금지**.
   - 내부 처리 로직(쿼리, 서비스 함수, 헬퍼)은 자유롭게 정리·수정 가능.
   - 입출력 변경이 꼭 필요해 보이는 경우 → **`02_CHANGE_REQUESTS.md`에만 등록**, 즉시 수정 금지. 추후 프런트와 합의 후 일괄 적용.

2. **하나씩, 순차적으로**
   - main / core 등 공통 인프라 → 라우터 단위 → 서비스 단위.
   - 한 단위 검토가 끝나기 전에 다음 단위로 넘어가지 않는다.

3. **수정 vs 등록**
   - 사소한 정리/주석/dead code 제거 같은 "안전한" 수정은 즉시 반영해도 됨.
   - 동작 변경, API 변경, 리팩토링 큰 건은 모두 `02_CHANGE_REQUESTS.md`에 등록 후 진행 결정.

4. **검토 기록**
   - 각 단위 검토는 일자별 작업 로그(`08_TODAY_WORKLOG_*.md`, `10_CODE_CLEANUP_*.md`)에 누적 기록.
   - 사용자가 던진 질문과 응답도 같은 파일에 시간순으로 기록.

---

## 1. 검토 단위 (실행 순서)

### Phase 1 — 공통 인프라 (필수 코드)

| # | 대상 | 비고 |
|---|---|---|
| 1.1 | `backend/main.py` | FastAPI 부트스트랩, lifespan, 미들웨어, CORS, docs 보호 |
| 1.2 | `backend/core/config.py` | 환경변수 / Settings |
| 1.3 | `backend/core/database.py` | 엔진/세션팩토리/`get_db` |
| 1.4 | `backend/core/security.py` | `verify_credentials` (Basic + X-Admin-API-Key) |
| 1.5 | `backend/core/enums.py` | `OrderStatus`, `ServingTemperature`, `SessionStatus` 등 |
| 1.6 | `backend/model.py` | SQLAlchemy ORM 전체 |
| 1.7 | `backend/schemas.py` | Pydantic 스키마 전체 (응답 호환성 핵심) |
| 1.8 | `backend/api/v1/router.py` | 서브라우터 조립 |

### Phase 2 — 도메인별 라우터 + 서비스 + CRUD

각 도메인은 **엔드포인트(`api/v1/endpoints/*.py`) → 서비스(`services/*_service.py`) → CRUD(`crud/*.py`)** 순으로 한 묶음씩 검토.

| # | 도메인 | 엔드포인트 | 서비스 | CRUD |
|---|---|---|---|---|
| 2.1 | Kiosk / Auth | `kiosk.py` | — | `kiosk.py` |
| 2.2 | Session | `session.py` | — | `session.py` |
| 2.3 | Menu | `menu.py` | — | `menu.py` (메뉴 부분) |
| 2.4 | Option | `option.py` | — | `menu.py` (옵션 부분) |
| 2.5 | Cart | `cart.py` | `cart_service.py` | `cart.py` |
| 2.6 | Order | `order.py` | `order_service.py` | `order.py` |
| 2.7 | Analytics | `analytics.py` | `analytics_service.py` | — |
| 2.8 | Recommendation | `recommendation.py` | `recommendation_service.py` | `recommendation.py` |
| 2.9 | Vision / Face | `vision.py` + `face.py` | `vision_service.py` + `face_service.py` | `vision.py` |
| 2.10 | Voice / Chat | `voice.py` | `chat_service.py` + `voice_matching.py` + `voice_prompting.py` + `canned_responses.py` | `chat.py` |
| 2.11 | Trend | (recommendation 내) | `trend_service.py` | — |
| 2.12 | Logs | `logs.py` | — | (session_activity_logs) |

### Phase 3 — 보조

| # | 대상 |
|---|---|
| 3.1 | `backend/scripts/seed_menu.py` |
| 3.2 | `backend/scripts/bootstrap_recommendation_data.py` |
| 3.3 | `backend/scripts/verify_voice_pipeline.py` |

### Phase 4 — 프런트엔드 (별도 합의 후)

본 검토는 백엔드 우선. 프런트는 추후 별도 라운드.

---

## 2. 각 단위 검토 시 체크리스트

매 단위마다 다음 7개 관점으로 본다.

1. **의도된 동작과 일치하는가** — 함수/엔드포인트 docstring · 호출처 의도 vs 실제 코드.
2. **불필요한 코드** — dead code, 미사용 import, 사용되지 않는 분기, 중복 헬퍼.
3. **효율성** — N+1 쿼리, Python에서 할 일 vs DB에서 할 일, 불필요한 reload.
4. **에러 처리** — 예외 누수, 잘못된 fallback, 사용자에게 의미 없는 메시지.
5. **시간대 / 인코딩 / NULL** 같은 경계 조건.
6. **보안 / 권한** — 관리자 인증 누락, 입력 검증 부재.
7. **API 입출력 호환성 (불변 원칙)** — 변경이 필요해 보이면 등록만 하고 보류.

---

## 3. 산출물 / 문서 구조

```
docs/review/
├── 00_REVIEW_PLAN.md                ← 본 문서. 계획.
├── 02_CHANGE_REQUESTS.md            ← 수정해야 할 항목 목록. 즉시 vs 보류 구분.
├── 03_DATA_VALIDATION.md            ← 합성 데이터 검증 가이드.
├── 05_DATASET_CANDIDATES.md         ← 외부 데이터 후보 평가 (캡스톤 보고서 references).
├── 07_RECOMMENDATION_REWORK_PLAN.md ← 통계 추천 + 합성 데이터 채택 / backend 재정비 계획.
├── 08_TODAY_WORKLOG_2026-05-05.md   ← 일자별 작업 로그 (추천 데이터 결정).
├── 09_BACKEND_INTEGRATION_PLAN.md   ← v2 합성 데이터 backend 적용 가이드.
└── 10_CODE_CLEANUP_2026-05-05.md    ← 코드 정리 라운드 + 추후 할 일.
```

> 단위별 검토 로그는 `08_*.md`, `10_*.md` 같은 일자별 작업 로그로 통합되어 있다.
> 옛 `01_REVIEW_LOG.md` (빈 템플릿), `04_EXTERNAL_DATA_SEARCH.md` (모델형 거부됨), `06_NOTEBOOK_PLAN.md` (모델 노트북 REJECTED) 는 사용 중단되어 삭제.

- `02_CHANGE_REQUESTS.md`: 표 형식.
  - ID / 대상 파일 / 분류(즉시/보류/API변경) / 내용 / 영향 범위 / 결정.

---

## 4. 오늘 검토 목표

오늘은 **Phase 1 (공통 인프라) 전부**를 끝내는 것을 목표로 한다.
- 1.1 main.py
- 1.2 core/config.py
- 1.3 core/database.py
- 1.4 core/security.py
- 1.5 core/enums.py
- 1.6 model.py
- 1.7 schemas.py
- 1.8 api/v1/router.py

Phase 2는 별도 세션에서 도메인 단위로 진행한다.

---

## 5. 진행 방식 (대화 흐름)

1. 사용자가 `1.1 main.py 시작` 같은 신호를 줌.
2. 어시스턴트가 해당 파일을 끝까지 읽고 **체크리스트 7개 관점으로 분석한 결과**를 답변.
3. 사용자가 궁금한 부분 질문 → 어시스턴트 답변 → 두 흐름 모두 일자별 작업 로그에 기록.
4. 수정 결정이 나면:
   - 안전한 수정 → 즉시 반영하고 로그에 "적용함" 표기.
   - 큰 변경 → `02_CHANGE_REQUESTS.md`로 이관.
5. 한 단위가 끝나면 다음 단위로.

---

## 6. 약속된 제약 사항 정리

- ❌ 기존 API request/response **JSON 형태 변경 금지** (필드 추가/삭제/이름 변경/타입 변경).
- ❌ 라우트 경로/메서드 변경 금지 (신규 추가는 가능).
- ✅ 내부 로직, 쿼리, 서비스 함수 시그니처(내부용) 변경 자유.
- ✅ 신규 엔드포인트 추가 가능. 단 기존 프런트가 의존하지 않는 것이 확인된 후.
- ⚠️ DB 스키마 변경(컬럼/인덱스/테이블)은 마이그레이션 영향 큼 → 모두 `02_CHANGE_REQUESTS.md`로.

---

## 7. 변경 적용 시 항상 지킬 것

- 변경 후 `python -m py_compile <파일>` 로 즉시 통과 확인.
- 프런트 영향이 의심되면 그 파일이 `frontend/src/utils/api.js`나 `adminApi.js` 호출처에 있는지 grep으로 교차 확인.
- 시간대/인코딩 관련 변경은 항상 "DB 저장 = UTC 가정, 표시 = KST" 원칙을 명시.
