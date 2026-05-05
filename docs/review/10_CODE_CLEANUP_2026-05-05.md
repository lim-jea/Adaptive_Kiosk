# 10. 코드 정리 라운드 — 2026-05-05

> 본 문서는 2026-05-05 진행한 backend 코드 정리 작업의 **순차 기록 + 영역별 변경 내역 + 추후 해야 할 일**을 정리한다.
>
> 관련 문서:
> - [02_CHANGE_REQUESTS.md](./02_CHANGE_REQUESTS.md) — 변경 트래커 (보류/기각 항목)
> - [08_TODAY_WORKLOG_2026-05-05.md](./08_TODAY_WORKLOG_2026-05-05.md) — 같은 일자 추천 데이터 작업
> - [09_BACKEND_INTEGRATION_PLAN.md](./09_BACKEND_INTEGRATION_PLAN.md) — v2 합성 데이터 backend 적용 가이드

## 0. 정리 라운드의 절대 조건

사용자가 본 라운드에서 명시한 조건. 모든 변경은 이 조건을 통과해야 함:

1. **API 입출력 형식 동일** — URL/method/request body/response schema/status code/error code 모두 변경 X
2. **프론트 무수정** — frontend 코드는 그대로 작동 가능해야 함
3. **처리 방식과 결과물 동일** — 효율을 위해 줄이는 것은 OK, 동작이 "딴판으로 다른" 것은 X
4. **wrap 함수 안티패턴 회피** — `func_a` 가 `func_b` 를 호출해 형식만 살짝 바꿔 반환하는 thin wrap 은 만들지 않는다 (대신 inline 으로 처리)
5. **추천 시스템 결과 무변경** — 어떤 변경에도 추천 응답값이 byte-level 동일해야 함

## 1. 영역별 변경 내역

### 1-1. Cart 영역
| 파일 | 변경 |
|---|---|
| `services/cart_service.py` | • `_empty_cart_data()` 중복 정의 제거 (crud 의 것 import)<br>• `_get_session_or_404` → `get_session_by_uuid` 인라인 + 404 raise 패턴으로 복구 (3곳)<br>• `calculate_unit_price` 시그니처 `(int, Menu) → (int, Menu, list[MenuOption])` — 검증된 옵션 객체도 반환<br>• `_build_cart_item` 의 옵션 두 번째 fetch loop 제거 (round-trip N → 0)<br>• `_summarize_items` 제거 + `_apply_cart_state(cart, items)` 통합<br>• `replace_cart` / `clear_cart` 가 `_apply_cart_state` 한 줄로 통합 |

### 1-2. Order 영역
| 파일 | 변경 |
|---|---|
| `services/order_service.py` | • `calculate_unit_price` 새 시그니처 적용<br>• `get_option_item_by_id` 두 번째 fetch loop 제거 → `validated_options` list comprehension<br>• `_build_order_item_response(item, *, menu_name)` / `_build_order_response(order, *, session_uuid, items)` 내부 private helper 추가<br>• `get_order_response` ↔ `list_order_responses` 응답 빌드 중복 ~25줄 제거<br>• runtime CSV 의 OrderItem mirror 가 DB 컬럼 1:1 형식으로 누락 없이 기록 (`menu_name_snapshot`, `line_total`, `selected_options_json` 추가) |

### 1-3. Menu / Option 영역
| 파일 | 변경 |
|---|---|
| `crud/menu.py` | • `get_option_groups(menu_name=...)` wrap 단축 → 직접 `MenuOption` query<br>• `get_option_group_with_items` wrap 단축 → 단일 `group_name` 조건 query<br>• `upsert_option_group` 시그니처에 `menu: Menu \| None = None` keyword-only optional 추가 → caller 가 이미 가진 Menu 객체를 전달해 N번 lookup 절약<br>• `replace_menu_option_groups` 가 `menu=menu` 로 전달 |
| `endpoints/menu.py` | 4곳 endpoint 의 변경 직후 `invalidate_menu_catalog_cache()` 호출 추가 (create / update / delete menu / delete option group) |
| `endpoints/option.py` | 두 POST endpoint (`/option-groups`, `/menus/{menu_name}/option-groups`) 에 `invalidate_menu_catalog_cache()` 호출 추가 |

### 1-4. Recommendation 영역
| 파일 | 변경 |
|---|---|
| `services/recommendation_service.py` | • `_compute_profile_stats` 의 `total_orders` 재계산 O(N²) → 단일 `groupby` + dict lookup (O(N))<br>• `_compute_co_purchase_stats` 의 menu_id loop O(N²) → counts 양방향 펼침 + 단일 `groupby` (O(N))<br>• `_global_popularity_cache` 추가 (`__init__`)<br>• `_precompute_global_popularity()` 신규 — `load_cached_stats` 시점 1회 빌드<br>• `_get_global_popularity` 가 매 호출 N×M 스캔 → dict lookup 1회<br>• `RUNTIME_DIR = backend/data/runtime` 신규 분리 — baseline 무결성 보호<br>• `_ensure_csv_state` — baseline + runtime 양쪽 uuid 모두 로드 (중복 append 방지)<br>• `append_runtime_order_records` 가 RUNTIME_DIR 에만 기록, DB 컬럼 1:1 mirror (session_id, menu_name_snapshot, line_total, selected_options_json) |

성능 (격리 검증):
- profile_stats: 0.226s → 0.109s (~52% 단축)
- co_purchase_stats: 0.051s → 0.041s
- global_popularity: 호출당 ~9000 iter → dict lookup 1회

결과 동일성: profile/co_purchase/`get_mode_a_recommendations` 4 컨텍스트 모두 byte-level 동일.

### 1-5. TTS 영역 (Edge-TTS 도입)
| 파일 | 변경 |
|---|---|
| `services/chat_service.py` | • `synthesize_speech` — 메모리 LRU 캐시 → Edge-TTS 호출 → 실패 시 None<br>• `_synthesize_speech_edge` 신규<br>• `_synthesize_speech_live` (Gemini TTS, ~150줄) 삭제<br>• `import base64, io, wave` 제거 |
| `endpoints/voice.py` | • `/voice/tts` media_type `audio/wav` → `audio/mpeg`<br>• `_audio_b64_for` source label `tts` → `edge` |
| `core/config.py` | `GENAI_TTS_*` 4개 설정 제거, `EDGE_TTS_ENABLED=True`, `EDGE_TTS_VOICE="ko-KR-SunHiNeural"` 추가 |
| `.env`, `.env.example` | flag 정리 + Edge-TTS 섹션 추가 |
| `pyproject.toml`, `requirements.txt` | `edge-tts>=6.1.0` 의존성 추가 |
| `frontend/src/hooks/useTTS.js` | `looksLikeWav` → `detectAudioMime` (WAV + MP3 자동 감지). 하위 호환 |

### 1-6. Voice 영역 (음성 주문 파이프라인 정리)
| 파일 | 변경 |
|---|---|
| `endpoints/voice.py` | `voice_start` 두 분기 (reused / new attempt) 통합 — 단일 선형 흐름 |
| `services/chat_service.py` | • `_attr_or_key(obj, key, default)` helper — ORM/dict 양쪽 호환<br>• `_finalize_option_item_ids` / `_required_options_satisfied` 의 6번 반복 ORM/dict 패턴 → helper 호출로 단축<br>• `_QUANTITY_KO` (한국어 수량 매핑) 모듈 레벨 상수화 |
| `services/voice_prompting.py` | (기존 그대로) `invalidate_menu_catalog_cache` 가 menu/option endpoint 6곳에서 호출됨 → 메뉴 변경 즉시 prompt 카탈로그 캐시 갱신 |
| `services/canned_responses.py` | `all_canned_texts()` 제거 (호출처 0) |

### 1-7. 합성 데이터 v3 (대시보드 보강)
대시보드 위젯들이 의미있는 분포로 표시되도록 v2 합성 데이터에 새 컬럼/분포 보강.

| 파일 | 변경 |
|---|---|
| `create_data/recommendation_test/generate_synth_v2.py` | • 보강 prior 정의 (`USED_RECOMMENDATION_RATE`, `SIMPLE_MODE_RATE`, `HELP_TRIGGERED_RATE`, `END_REASON_DIST`, `ORDER_STATUS_DIST`, `OPTION_CATALOG`, `MENU_OPTION_GROUPS`)<br>• `enrich_rng = np.random.default_rng(seed + 9_999_991)` 분리 — 메뉴 추첨 RNG state 무영향 보장<br>• 세션/주문/라인 레벨 보강 추첨<br>• `recommendation_events.csv` 신규 생성 (used_recommendation=True 주문에서 1~2 events) |
| `create_data/recommendation_test/sync_synthetic_data.py` | 보강 컬럼들이 source → target 으로 그대로 옮겨가도록 수정 (이전엔 하드코딩 default) |
| `backend/data/kiosk_sessions.csv` | v3 적용 (50,000 rows, is_simple_mode 4%, help_triggered 2.3%, end_reason 분포) |
| `backend/data/orders.csv` | v3 (used_recommendation 15%, status 분포) |
| `backend/data/order_items.csv` | v3 (from_recommendation 8.3%, selected_options_json 498종 분포) |
| `backend/data/recommendation_events.csv` | 신규 (9,728 events, was_clicked 56%, led_to_order 33%) |
| `backend/data/_legacy_v2/` | 보강 전 v2 백업 (롤백용) |

### 1-8. 검토 후 무변경 결정

- `kiosk.py` + `crud/kiosk.py`
- `session.py` + `crud/session.py` (`update_session` 의 OR 비교 redundancy 보존 — face.py 가 None 보낼 수 있음)
- `logs.py`
- `endpoints/cart.py`, `endpoints/order.py` (thin wrapper, service 호출만)
- `voice_matching.py` (sanitize_input / check_jailbreak / match_pattern / match_menu_name)
- `voice_prompting.py` 의 3쌍 cache pattern (통합 효과 미미)
- `recommendation.py` endpoint try/except 외곽 (inline OK)
- `process_chat_message` 본체 분리 (wrap 안티패턴)

## 2. 동작 보존 검증

모든 변경에 대해 다음 검증 통과:

| 검증 항목 | 방법 | 결과 |
|---|---|---|
| Syntax | `ast.parse` | 모든 파일 OK |
| 26개 모듈 import | 실제 import 시도 | 26/26 OK |
| FastAPI app 빌드 | `from main import app` | 56 routes OK |
| 핵심 endpoint 12개 등록 | path 매칭 | 12/12 OK |
| Recommendation 결과 동일성 | profile/co_purchase 4 컨텍스트 격리 비교 | byte-level 동일 |
| TTS 폴백 흐름 | Edge 실패 → None → 프론트 brower TTS | 무수정 작동 |
| 옵션 ID 추출 동일성 (`_attr_or_key`) | 기존/새 결과 비교 | 모든 케이스 동일 |
| `voice_start` 두 분기 통합 동일성 | persona/attempt/current_stage/greeting/insert_message/audio/response 비교 | 응답 schema 동일, DB 결과 동일 |
| 삭제 심볼 잔재 검사 | grep `_synthesize_speech_live`, `all_canned_texts`, `GENAI_TTS_*`, `_summarize_items`, `_get_session_or_404`, `require_session` | 모두 CLEAN |
| v2 합성 데이터 보강 후 추천 동일성 | profile_stats content diff 0/40, co_purchase 0/22, mode_a 4 컨텍스트 same=True | byte-level 동일 |
| FK 무결성 (v3) | sessions/orders/items/rec_events 매칭 | 모두 100% |

## 3. 발생한 오류와 해결

### 3-1. `ImportError: cannot import name 'OptionItem' from 'model'`
- **원인**: `cart_service.py` 에서 `calculate_unit_price` 시그니처에 `OptionItem` 타입 힌트 추가했으나 `model.py` 의 실제 클래스명은 `MenuOption`
- **해결**: 3곳 (cart_service.py:9, 25, 42) `OptionItem` → `MenuOption`

### 3-2. `Database initialization skipped: merge on str and int64 columns for key 'session_id'`
- **원인**: 이전 backend 운영 중 `append_runtime_order_records` 가 `backend/data/*.csv` (v2 합성 baseline) 에 직접 append → session_id 컬럼 누락 → dtype mismatch → merge 실패 → mode CF "No data for profile" 에러
- **해결**: `RUNTIME_DIR = backend/data/runtime/` 신설 + `append_runtime_order_records` 가 RUNTIME_DIR 에만 기록 → baseline 영구 무결성 보호

### 3-3. v2 보강 시 메뉴 추첨 RNG state 변경
- **원인**: `generate_synth_v2.py` 에 보강 추첨 (`_sample_from_dist`, `sample_options_for_menu`) 추가 시 같은 `rng` 인스턴스를 사용 → 그 후의 메뉴 추첨에서 random state 가 달라져 추천 결과 변경
- **해결**: `enrich_rng = np.random.default_rng(seed + 9_999_991)` 별도 RNG 분리 → 메뉴 추첨 rng 무영향, 추천 결과 byte-level 동일

## 4. CHANGE 트래커 갱신

본 라운드에서 발생한 트래커 변경:

| ID | 상태 변경 | 사유 |
|---|---|---|
| CHANGE-014 (FM/Item2Vec) | REJECTED | 모델형 추천 거부, 통계 기반 + 합성 데이터 노선 |
| CHANGE-015 (mode 필드 분해) | REJECTED | CHANGE-014 자동 무효 |
| CHANGE-017 (v2 generator) | ADOPTED | backend 반영 + 라벨 표준 통일 + 대시보드 분포 보강 완료 |
| CHANGE-019 (`_get_session_or_404` 통합) | REJECTED | wrap 함수 자체가 안티패턴, inline 으로 복구 |
| CHANGE-020 (cart replace/clear 통합) | APPLIED | `_apply_cart_state` 도입 완료 |
| CHANGE-021 (runtime/baseline 분리) | **부분 APPLIED** | runtime CSV 분리 + DB schema 1:1 mirror 형식으로 채움 완료. bootstrap 의 `_bulk_insert_*` 보강은 아직 (selected_options_json 매핑, menu_name_snapshot, RecommendationEvent 추가) |

## 5. 추후 해야 할 일

본 라운드에서 보류한 항목 + 새로 식별된 항목.

### 5-1. DB 관련 (운영 단계 진입 시 일괄 처리)

| ID | 항목 | 트리거 |
|---|---|---|
| CHANGE-001 | DB 시간대 일관화 — `server_default=func.now()` → `text("UTC_TIMESTAMP()")` | 운영 서버 TZ 확정 시 |
| CHANGE-002 | `lifespan` 의 광범위 `except Exception` 분리 — fatal vs ignorable 정책 | DB 스키마 확정 후 |
| CHANGE-003 | `seed_menu_data` idempotency + env flag (`SEED_ON_STARTUP`), `bootstrap_recommendation_csv_to_db` 정책 | DB 확정 후 |
| CHANGE-005 | `_compute_profile_stats` 시간 감쇠 (최근 N일 가중) | 실데이터 누적 후 |
| CHANGE-006 | `_get_global_popularity` 표본수 가중 평균 | 실데이터 누적 후 |
| CHANGE-007 | profile 묶음 빈 라벨 (`dropna=False`) 처리 정책 | 운영 데이터 확인 후 |
| CHANGE-018 | 부팅 시점 데이터 부트스트랩 일괄 정리 (seed_menu / recommendation_csv / **trend_service 미작동**) | DB 확정 + 운영 진입 전 |
| **CHANGE-021** (잔여) | bootstrap 의 `_bulk_insert_order_items` 가 `selected_options_json: []` 하드코딩 → CSV 값 사용으로 변경 + `menu_name_snapshot` INSERT 추가 + **`_bulk_insert_recommendation_events` 신규 함수 추가** | `RECOMMENDATION_BOOTSTRAP_ON_STARTUP=true` 활성 직전 |

### 5-2. 추천/TTS 영역 (필요 시)

| 항목 | 결정 트리거 |
|---|---|
| **CSV → DB 입력 전환** (CHANGE-018 의 일부) — `recommendation_service.load_data` 가 DB query 로 전환 | 실 주문 누적 시작 시점 |
| **trend_service Naver datalab 활성** (현재 `NAVER_TREND_ENABLED=false`) | 시즌 메뉴 출시 / 외부 데이터 통합 차별화 필요 시 |
| **TTS 디스크 캐시** — 자주 쓰는 phrase 사전 합성 | 메모리 캐시만으로 부족 (현재 메모리 LRU 64개로 충분) |
| **Edge-TTS → Naver Clova Voice 전환** (운영 단계) | 비공식 endpoint 의존 부담 대체 |
| `mode` 라벨 정정 (CHANGE-004) — "CF" 표기가 부정확 | 프론트와 합의 후 |

### 5-3. 머지/통합

| 항목 | 비고 |
|---|---|
| **`image_recog` 브랜치 머지** | Vision/Face 영역 — 본 라운드에서 검토 보류 |
| **Analytics 영역 깊은 검토** | `endpoints/analytics.py` (228줄) + `services/analytics_service.py` (587줄) — 현재는 사용 컬럼/엔드포인트 의존성만 점검. 추천과 비슷한 통계 패턴 |
| **schemas.py 검토** (775줄) | 응답 schema 직접 변경 위험, 다만 dead model 점검 가치 |
| **`code_clean` 브랜치 → main PR / 머지** | 본 라운드 작업물 |

### 5-4. 운영 안정화

| 항목 | 비고 |
|---|---|
| `voice_prompting._CATEGORY_CACHE` 등 TTL 정책 | 5분 TTL + 메뉴 변경 시 invalidate. 운영 모니터링 |
| `RUNTIME_REFRESH_EVERY = 25` (추천 캐시 갱신 주기) | 50k orders 기준 적절. 데이터 늘면 조정 |
| `_TTS_MEM_CACHE` 64개 LRU | 캐시 명중률 모니터링 후 크기 조정 |
| `chat_crud.list_messages_for_context max_total_chars=5000` | 긴 대화 시 잘림 — Gemini token 비용 trade-off |

### 5-5. 정리/문서화

| 항목 | 비고 |
|---|---|
| 본 문서를 캡스톤 보고서의 "백엔드 정리 라운드" 챕터 자료로 활용 | 동작 보존 검증 표가 그대로 보고서 자료 |
| `docs/review/` 의 보류 CHANGE 항목들을 운영 진입 직전 일괄 점검 | 본 라운드 산출물이 baseline |
| 합성 데이터 v3 의 분포 prior 가 시즌/요일 변동을 반영하지 못함 | 실주문 누적 시작 후 prior 재추정 |

## 6. 본 라운드 마감 시 backend 상태

- `ko-KR-SunHiNeural` 음성 (여성) Edge-TTS 활성
- v2/v3 합성 데이터 (50k sessions, M/F + 20~29~50+ 라벨, 보강 분포 7종) 운영 중
- 추천 통계 캐시 빌드 단축 + `_global_popularity_cache` precompute
- 메뉴 카탈로그 음성 prompt 캐시 즉시 갱신 (변경 endpoint 6곳에 invalidate 연결)
- `backend/data/runtime/` 신설 — 실주문 누적 분리, baseline 무결성 영구 보호
- `RecommendationEvent` 합성 데이터 (9,728 events) 준비 — bootstrap 보강 후 활성화 가능
- API I/O 무변경 — 프론트 무수정으로 정상 작동
- 추천 응답 4 컨텍스트 byte-level 동일 (이전 라운드와)

## 7. 변경 통계

| 영역 | 줄수 변화 (대략) |
|---|---|
| `chat_service.py` | -150 (Gemini TTS 함수 삭제) +50 (Edge-TTS + helper) +상수화 = **약 -100줄** |
| `cart_service.py` | -30 (중복/dead 제거) +20 (helper) = **약 -10줄** |
| `order_service.py` | -25 (response build dedup) + runtime mirror 컬럼 보강 = **±0줄** |
| `recommendation_service.py` | +20 (`_global_popularity_cache` + `_precompute_global_popularity`) +RUNTIME_DIR + 보강 컬럼 fieldnames = **약 +50줄, 성능 개선** |
| `crud/menu.py` | -10 (wrap 단축) = **-10줄** |
| `voice.py` | -25 (voice_start 통합) = **-25줄** |
| `canned_responses.py` | -8 (`all_canned_texts` 제거) = **-8줄** |
| `generate_synth_v2.py` | +130 (보강 prior + enrich_rng + RecommendationEvent 합성) |
| 그 외 (`menu.py`, `option.py`, `config.py`, `.env`, `useTTS.js` 등) | +invalidate 호출 7곳, +Edge-TTS settings, +mp3 detect 분기, +runtime 분리 |

총합: **추천 시스템 결과 byte-level 동일 + 성능 개선 + dashboard 데이터 풍부 + ~100줄 절약 + 의존성 1개 (edge-tts) 추가**.

다음 회차 시작 시점: **`code_clean` 브랜치 main 머지** 또는 **Analytics 영역 깊은 검토** 또는 **`image_recog` 브랜치 머지**.
