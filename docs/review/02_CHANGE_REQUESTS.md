# 변경 요청 트래커

> 검토 계획: [00_REVIEW_PLAN.md](./00_REVIEW_PLAN.md)
> 일자별 작업 로그: [08_TODAY_WORKLOG_2026-05-05.md](./08_TODAY_WORKLOG_2026-05-05.md), [10_CODE_CLEANUP_2026-05-05.md](./10_CODE_CLEANUP_2026-05-05.md)

검토 중 발견된 **수정 필요 항목**을 모은다.
즉시 적용은 로그에만, 여기엔 **합의/지연이 필요한 변경**을 등록한다.

---

## 표기 규칙

- **ID**: `CHANGE-001` 부터 순차.
- **분류**:
  - `즉시` — 안전한 정리, 본 검토 세션에서 곧바로 반영하기로 결정.
  - `보류-내부` — 내부 로직 수정. API 영향 없음. 다음 검토 라운드 또는 별도 작업으로 진행.
  - `보류-API` — API 입출력에 영향. **프런트와 합의 후** 진행.
  - `보류-DB` — DB 스키마/마이그레이션 영향. 별도 마이그레이션 계획 필요.
- **상태**: `등록 / 합의대기 / 진행중 / 완료 / 기각`.

---

## 등록 표

| ID | 분류 | 대상 | 내용 | 영향 범위 | 상태 | 결정/메모 |
|----|------|------|------|----------|------|-----------|
| CHANGE-001 | 보류-DB | `backend/model.py` `created_at` 등 | DB 저장 시각의 일관성: `server_default=func.now()`가 서버 TZ에 의존 → `text("UTC_TIMESTAMP()")`로 명시화 마이그레이션 검토 | 모든 시간대 분석 | 등록 | 운영 서버 `time_zone` 확인 후 결정 |
| CHANGE-002 | 보류-내부 | `backend/main.py` lifespan | 광범위 `except Exception`이 DDL/시드/부트스트랩 실패를 모두 삼키고 warning만 남김 → 운영에선 부분 실패가 silent로 숨겨짐 | 부팅 신뢰성 | 등록 | DB 확정 후 시드 실패 분리(fatal vs ignorable) 정책 수립 |
| CHANGE-003 | 보류-내부 | `backend/main.py` lifespan + `backend/scripts/seed_menu.py` | DB 확정 후 부트스트랩 정리: ① `seed_menu_data` idempotency 확인 후 env flag로 가드(`SEED_ON_STARTUP=false` 운영 기본), ② `bootstrap_recommendation_csv_to_db`는 코드 유지하되 env false 유지 (현재 그대로 운영 가능) | 부팅 동작 | 등록 | Phase 2.3 메뉴 검토에서 `seed_menu_data` idempotency 먼저 검증 필요 |
| CHANGE-004 | 보류-API/내부 | `backend/services/recommendation_service.py` 응답·docstring·`mode` 라벨 | "CF(협업 필터링)"이라는 명명이 부정확 — 실제는 세그먼트별 인기도 + item-item co-occurrence + 외부 트렌드 가중치의 휴리스틱 결합. 학습된 모델 없음. 응답 `"mode": "CF"`/모듈 docstring을 정정 (예: `"heuristic"` 또는 `"popularity+co_purchase"`) | 추천 응답 mode 필드 — **프런트와 합의 필요** | 등록 | mode 필드를 프런트가 사용 중인지 확인. 문구만 정정할지, 필드 자체를 변경할지 합의 |
| CHANGE-005 | 보류-내부 | `backend/services/recommendation_service.py` `_compute_profile_stats` | 모든 이력을 동일 가중치로 합산 → 트렌드 변화·시즌성 반영 늦음. 최근 N일 가중 또는 시간 감쇠(exponential decay) 적용 검토 | 추천 결과 분포 | 등록 | 데이터 충분히 누적된 후 도입. 합성 데이터로 효과 검증 가능 |
| CHANGE-006 | 보류-내부 | `backend/services/recommendation_service.py` `_get_global_popularity` | 모든 묶음의 popularity를 단순 평균 → 묶음 표본 크기 무시. 표본수 가중 평균으로 변경 검토 | global fallback 점수 | 등록 | 작은 묶음의 노이즈가 평균에 동일 영향을 주는 문제 |
| CHANGE-007 | 보류-내부 | `backend/services/recommendation_service.py` profile 묶음 키 | `estimated_age_group`/`estimated_gender`가 빈 문자열인 세션도 자기 묶음을 형성(`dropna=False`). 의미 없는 fallback 묶음을 만들 수 있음 | 추천 결과 / 데이터 정합성 | 등록 | 합성·운영 데이터에서 빈 라벨 발생 비율 확인 후 결정 (skip vs unknown 그룹으로 합치기) |
| CHANGE-008 | 보류-내부 | `create_data/build_dataset.py` | 합성 데이터 보강 — D-01~D-07 일괄 처리: ① `keep` 비교 안전화, ② datetime UTC 명시, ③ 의사 사용자(`pseudo_user_id`) 추가, ④ 매핑 누락 통계 로깅, ⑤ `recommendation_events.csv` 생성, ⑥ `order_items.selected_options_json` 합성, ⑦ validation 보강(시간/외래키/co-purchase) | 데이터 품질 / 추천 정확도 | 등록 | 모델 기반 CF 도입(CHANGE-004) 결정과 함께 묶어서 진행. 03_DATA_VALIDATION.md §5-A 참조 |
| CHANGE-009 | 보류-내부 (긴급) | `create_data/build_dataset.py` 주문 단위 그룹핑 | **현재 한 주문 안에 다른 메뉴가 함께 있는 경우가 0건** → co-purchase 시그널이 완전히 사망. `transaction_id` 단위 그룹핑 + 같은 시간대·동일 영수증 가정의 한계. 해결: ① 인접 transaction을 같은 세션으로 묶는 합성 규칙(예: 같은 시각 ±2분 내 트랜잭션을 한 주문으로 병합) 또는 ② 카탈로그 기반 페어 분포(예: 아메리카노+케이크)를 의도적으로 삽입 | 추천 co-purchase 시그널 전체 | 등록 | 검증 SQL: `SELECT COUNT(*) FROM order_items GROUP BY order_id HAVING COUNT(DISTINCT menu_id) >= 2` 가 0이 아니어야 함 |
| CHANGE-010 | 보류-내부 (긴급) | `create_data/build_dataset.py:354-355` 인구통계 합성 | **gender/age_group이 메뉴와 독립적인 weighted random** → 모든 (성별×연령대×시간) 묶음의 메뉴 분포가 거의 동일 → `_compute_profile_stats`의 의미 무효화. 해결: 메뉴별 가중 prior(예: 라떼류는 20대 여성에 가중, 아메리카노는 30대 남성에 가중)를 카탈로그에 정의해 샘플링 | profile_popularity 시그널 전체 | 등록 | 검증 SQL: 각 (성별,연령대) 묶음의 top 3 메뉴가 묶음마다 달라야 의미 있는 개인화 |
| CHANGE-011 | 보류-내부 | `create_data/build_dataset.py` ALLOWED_SOURCE_CATEGORIES + 키워드 매칭 | 카탈로그 22개 중 데이터에 살아남는 메뉴가 4개뿐 (82% 손실). 매핑 키워드 풀 보강 또는 카탈로그를 데이터에 맞게 축소 | 메뉴 다양성 / 추천 품질 | 등록 | 매핑 누락 카운트 로깅(D-04)과 함께 진행 |
| CHANGE-009 | **해소** | (기존 `create_data/build_dataset.py` 다중 라인 부재) | Phase 1.4 자체 합성에서 G 가설(다중 라인 30~50% + Bread Basket 페어 분포 매핑)로 직접 주입 | — | **CLOSED 2026-05-04** — 노트북 03 에서 처리 |
| CHANGE-010 | **해소** | (인구통계 × 메뉴 prior 부재) | OpenSurvey 응답에서 직접 prior 추출(Phase 1.1, 노트북 02) | — | **CLOSED 2026-05-04** |
| CHANGE-014 | **기각** | `backend/services/recommendation_service.py` | Item2Vec + FM 병렬 모델 도입 후보. 노트북 04~08 검증 결과 lift +0.7%p / 인구·컨텍스트 셔플 영향 ~0 / WEAK 1/5 → backend 통합 비채택. 학습 산출물은 Drive `output/artifacts/` 보존 | — | **REJECTED 2026-05-05** — [07_RECOMMENDATION_REWORK_PLAN.md](./07_RECOMMENDATION_REWORK_PLAN.md) |
| CHANGE-015 | **기각** | 추천 응답 스키마 | `fm_score`/`item2vec_score` 분해 필드 추가. CHANGE-014 기각으로 자동 무효 | — | **REJECTED 2026-05-05** |
| CHANGE-016 | 진행중 | `backend/data/{kiosk_sessions,orders,order_items}.csv` | 합성 데이터(OpenSurvey 기반)로 backend 추천 입력 데이터 교체. backend 코드 변경 없음. CHANGE-009/010/011 부분 해소 | 추천 품질 / 응답 분포 | 진행중 | `create_data/recommendation_test/` 격리 검증 후 반영. 후보=v2 (`data2/`). 적용 절차 [09_BACKEND_INTEGRATION_PLAN.md](./09_BACKEND_INTEGRATION_PLAN.md) |
| CHANGE-017 | 보류-내부 | `create_data/recommendation_test/generate_synth_v2.py` | v1 합성 데이터의 단일-메뉴 도배(말차 9.84%) + 컨텍스트 분리력 부족(unique top1 3/40) 해결. period × 메뉴 + (성별,연령) × 메뉴 prior 명시 + softmax cap 6% | 합성 데이터 품질 | **ADOPTED 2026-05-05** — 격리 검증 통과 + backend 반영 + 라벨 표준 통일(M/F + 20~29~50+) 완료. [08_TODAY_WORKLOG_2026-05-05.md](./08_TODAY_WORKLOG_2026-05-05.md) |
| CHANGE-018 | 보류-DB | backend 부팅 시점 데이터 부트스트랩 일괄 정리 — DB 확정 후 진행 | (1) `seed_menu_data` idempotency 검증 + env flag (`SEED_ON_STARTUP`), (2) `bootstrap_recommendation_csv_to_db` 정책 (현재 DB 비어있을 때만 INSERT — 부분 로드/upsert 가 필요한지), (3) **trend 데이터 부트스트랩/갱신이 현재 미동작** — Naver datalab 연동·캐싱·갱신 주기 미정. 부팅 시점 batch 가 없거나 trigger 가 불명확. (4) DB schema 가 확정·안정화된 시점에 (1)~(3) 일괄 점검 | 부팅 신뢰성 / 추천 trend 가중치 정확도 | 등록 (2026-05-05) | DB 확정 + 운영 진입 전까지 보류. CHANGE-002/003 와 묶어 처리 |
| CHANGE-019 | **기각** | 여러 endpoint/service 에 흩어진 `_get_session_or_404` 패턴 (cart_service.py, voice.py 등) | "단일 공유 helper 로 통합" 안 검토 → **wrap 함수 자체가 안티패턴**으로 결론. `get_session_by_uuid()` 는 직관적이고 이미 적절한 헬퍼이므로, 이를 다시 None-check + 404 만 해서 다른 함수로 wrap 하는 건 불필요한 간접층. **호출처에서 `get_session_by_uuid` 직접 호출 + inline None-check + raise 패턴** 으로 통일 | — | **REJECTED 2026-05-05** — 사용자 결정. 코드 정리 라운드에서 cart_service / voice.py 모두 inline 으로 복구 완료 |
| CHANGE-020 | 보류-내부 | `services/cart_service.py` `replace_cart` 와 `clear_cart` 의 중복 | 두 함수의 차이는 “items 리스트 비었는지” 뿐. mutation 본체를 `_apply_cart_state(cart, items)` 로 묶고 `clear_cart = replace_cart(items=[])` 로 통합. **endpoint 의 URL/method/body/response 는 그대로** (DELETE /carts/{uuid} 는 빈 items 로 PUT 하는 것과 동일 의미) | 코드 정리 | **APPLIED 2026-05-05** — `_apply_cart_state` 도입 완료 |
| CHANGE-021 | 보류-내부 | `backend/data/` baseline 과 실주문 로그 분리 | 현재 `append_runtime_order_records` 가 v2 합성 baseline 에 직접 append 하여 dtype 오염 + session_id 매칭 깨짐 → mode CF "No data for profile" 에러 유발. 분리 구조: (1) `backend/data/*.csv` = 합성 baseline (read-only), (2) `backend/data/runtime/*.csv` = 실주문 누적, (3) `load_data` 가 baseline + runtime concat. 안전을 위해 orders.csv 에 `session_uuid` 컬럼 추가 + runtime 매칭 robust 화. **현재 우선 조치**: `RUNTIME_ORDER_APPEND_ENABLED=false` 로 append 비활성 → baseline 영구 보호. | 추천 정확도 / 데이터 무결성 | 등록 (2026-05-05) | DB 확정 + 운영 진입 직전 일괄 구현. CSV → DB 전환 (CHANGE-018) 과 함께 진행 가능 |
| CHANGE-009 | **부분 해소** | (다중 라인 부재) | 합성 데이터 자체 G 가설(다중 라인 40%) + Bread Basket 페어 분포 매핑으로 신호 주입. CHANGE-016 반영 시 backend 적용 | — | **PARTIAL 2026-05-05** — v2 generator 의 Poisson(0.7) 다중라인으로 items/order=1.66 달성 |
| CHANGE-010 | **부분 해소** | (인구통계 × 메뉴 prior 부재) | OpenSurvey prior 기반 합성에서 정량 cosine 0.97로 재현. CHANGE-016 반영 시 backend 적용 | — | **PARTIAL 2026-05-05** — v1 단계 cosine 0.97 재현, 단 컨텍스트 분리력은 v2 의 `(gender,age)×menu` + `period×menu` 명시 prior 로 비로소 확보 |
| CHANGE-011 | **부분 해소** | (메뉴 매핑 손실 82%) | rec_items 30개 → backend 22개 매핑 5개 drop만으로 손실 17%로 축소 | — | **PARTIAL 2026-05-05** — v2 는 22 메뉴에 1:1 item_id 만 사용해 0% 손실 |

> 위 1번은 사전에 인지된 항목. 검토를 시작하면서 새 항목이 추가될 때마다 행을 늘린다.

---

## 항목 상세 (필요 시)

### CHANGE-001 — DB 시간대 일관화

- **현상**: `Order.created_at`, `KioskSession.started_at` 등 모든 시각 컬럼이 `server_default=func.now()`로 정의됨.
  MySQL/TiDB의 `NOW()`는 세션 `time_zone` 변수를 따른다.
- **현재 가정**: TiDB Cloud는 UTC 기본 → 코드(특히 `analytics_service._to_display_tz`)도 UTC 저장 가정.
- **위험**: 운영 서버 TZ가 KST로 바뀌면 모든 KST 변환이 +9h 이중 적용되어 어긋남.
- **제안**:
  1. `server_default=text("UTC_TIMESTAMP()")` 로 통일 (스키마 마이그레이션 필요, 무중단 가능).
  2. 또는 앱 시작 시 `SET time_zone = '+00:00'` 강제 (DB 권한 필요).
- **합의 필요 사항**: 운영 환경의 현재 `@@global.time_zone` 확인 후 1 또는 2 채택.

---

### CHANGE-002 — lifespan의 광범위 `except Exception` 정리

- **위치**: [backend/main.py:92-93](../../backend/main.py#L92-L93)
- **현상**: lifespan의 DB 초기화 블록 전체를 `try/except Exception`으로 감싸고 실패 시 `logger.warning("Database initialization skipped: %s", exc)`만 남김.
  - DDL 실패(잘못된 모델 정의), `seed_menu_data` 실패, `bootstrap_recommendation_csv_to_db` 실패, 추천 통계 batch 실패 모두 동일하게 무시됨.
- **위험**:
  - 시드 실패 시 키오스크 메뉴가 비어 있는 채로 앱은 정상 부팅 → 운영자가 인지하기 전까지 빈 화면.
  - 잘못된 모델로 일부 테이블만 만들어진 채 부팅되어 후속 쿼리에서 알 수 없는 오류.
- **제안**:
  - DDL/시드 실패는 **fatal**(부팅 중단)로 분리.
  - 추천 batch 같은 보조 작업은 warning 유지하되 **명확한 식별 로그**(어떤 단계가 실패했는지) 출력.
  - 추후 모니터링/알림 hook(예: Sentry, Slack)을 끼울 자리 마련.
- **선결 조건**: DB 스키마가 확정되어 시드/마이그레이션 흐름이 안정된 이후.
- **합의 필요 사항**: "어떤 단계가 fatal이고 어떤 단계가 ignorable인지" 정책 결정.

---

### CHANGE-003 — DB 확정 후 부트스트랩 정리

- **위치**: [backend/main.py:64-73](../../backend/main.py#L64-L73)
- **현상 1**: `seed_menu_data(db)`가 매 부팅마다 무조건 실행됨.
- **현상 2**: `bootstrap_recommendation_csv_to_db`는 `settings.RECOMMENDATION_BOOTSTRAP_ON_STARTUP` flag로 이미 가드됨. 현재 `.env`에서 `false`.
- **배경**: 개발 단계에서 DB 스키마/메뉴 데이터가 자주 바뀌어 자동 부트스트랩이 편의상 들어간 상태.
- **DB 확정 이후 처리 방향**:
  1. **`seed_menu_data` idempotency 확인**: "이미 같은 이름의 메뉴가 있으면 INSERT 건너뜀" 패턴인지 Phase 2.3에서 본체를 검토.
     - idempotent → 그대로 유지해도 안전. 매 부팅마다 no-op.
     - idempotent 아님 → 매 부팅마다 중복 row 생성 위험 → **즉시 fix 필요**.
  2. **운영 토글**: `SEED_ON_STARTUP` 같은 env flag로 감싸 운영에선 false로 유지하는 옵션 추가. 새 환경 배포 시에만 true로 한 번 부팅.
  3. **`bootstrap_recommendation_csv_to_db`**: 현재 구조 유지(flag 기반). 코드 삭제 불필요. 운영 시 `RECOMMENDATION_BOOTSTRAP_ON_STARTUP=false` 유지하고, 데이터 갱신 시점에만 잠시 true로.
- **선결 조건**: DB 스키마 확정 + `seed_menu_data` idempotency 검증 (Phase 2.3 메뉴 검토 시 함께).
- **참고**: `Base.metadata.create_all`은 빈 DB 자동 부팅용으로 유지가 적절. 단, 모델 변경 자동 반영은 안 되므로 운영에 가까워지면 Alembic 도입을 별도 후보로 고려.

---

## 신규 등록 시 양식

```markdown
| CHANGE-### | 보류-XXX | <파일/모듈> | <한 줄 요약> | <프런트/DB/내부> | 등록 | <메모> |
```

상세가 필요한 항목은 위 "항목 상세" 섹션에 별도 헤딩으로 추가.
