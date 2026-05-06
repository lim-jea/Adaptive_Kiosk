# 합성 데이터 검증 가이드

> 검토 계획: [00_REVIEW_PLAN.md](./00_REVIEW_PLAN.md)
> 관련 코드: [`backend/services/recommendation_service.py`](../../backend/services/recommendation_service.py) 의 `_compute_profile_stats`, `_compute_co_purchase_stats`, `_get_global_popularity`, `_get_profile_base_score`

---

## 0. 왜 이 문서가 필요한가

추천 엔진은 **DB의 과거 주문 이력**을 부팅 시점에 한 번 집계해서 메모리 캐시로 만든다. 즉 추천 품질은 **모델 변경 없이도 데이터가 바뀌면 바뀐다**. 캡스톤 단계에서는 운영 데이터가 부족하므로 **합성 데이터로 시뮬레이션**할 수밖에 없는데, 이 데이터의 분포가 어긋나면:

- "20대 여성 / 점심" 캐시가 비어 있어 추천이 작동하지 않거나,
- 한 메뉴만 압도적으로 많이 들어가 항상 그것만 추천되거나,
- 시간대 분포가 일률적이라 "아침/저녁" 차이가 사라지거나,
- 인구통계가 한 그룹에만 몰려 다른 그룹에는 fallback(global)만 돌아가는 등

**현장에서 보일 추천 결과가 의미를 잃는다**. 따라서 데이터 자체를 코드 검토와 동일한 수준으로 검증해야 한다.

---

## 1. 추천 엔진이 데이터에 의존하는 지점 (정확히)

`_compute_profile_stats`가 만드는 캐시는 다음 4단계에서 모두 쓰인다.

| 사용처 | 함수 | 데이터 의존 |
|---|---|---|
| 그룹별 인기 메뉴 후보 | `_get_profile_recommendations` | `(gender, age_group, period)` 묶음에 행이 있는지 |
| 그룹별 인기도 점수 | `profile_map[menu_id]` | 묶음 내 popularity 값 |
| 표본 크기 | `total_orders` | 묶음 내 distinct 주문 수 |
| 글로벌 fallback | `_get_global_popularity` | 모든 묶음의 popularity 평균 |
| 카트 연관 | `_compute_co_purchase_stats` | 한 주문 안에 함께 산 메뉴 |

→ **DB에 데이터가 없거나 한쪽으로 치우치면 이 다섯 군데가 동시에 망가진다.**

---

## 2. 합성 데이터 구성 시 반드시 채워야 하는 컬럼

### `kiosk_sessions`
| 컬럼 | 합성 시 주의 |
|---|---|
| `session_uuid` | UUID hex 32자 — 충돌 방지. |
| `kiosk_id` | 운영하려는 키오스크 ID 분포에 맞춰. 1대만 있어도 OK. |
| `started_at` | **`hour` 분포가 추천에 직접 영향**. 시간대(period)별 표본이 모두 차도록 분산. |
| `ended_at` | 체류시간 분석/세션 funnel에 사용. 통상 `started_at + N분`. |
| `is_simple_mode` | 간편모드 통계. 실제 비율(예: 20~30%) 흉내. |
| `estimated_age_group` | **추천 캐시 키의 일부**. 빈 문자열·NULL이면 별도 그룹으로 빠짐. **반드시 정의된 라벨**(예: 10대/20대/.../60대+)만 사용. |
| `estimated_gender` | 추천 캐시 키의 일부. F/M(또는 정의된 라벨)로 통일. |
| `help_triggered` | 도움요청 통계용. |
| `voice_persona`, `voice_current_stage` | 음성 흐름 분석. 채우지 않아도 추천에는 영향 없음. |

### `orders`
| 컬럼 | 합성 시 주의 |
|---|---|
| `order_uuid` | UUID hex 32자. |
| `session_id` | **반드시 위 `kiosk_sessions.id`와 매칭**되도록. join 안 되면 추천 데이터에서 제거됨. |
| `created_at` | 위 `started_at`과 같은 날짜·시간대 분포여야 자연스러움. **추천 시간대 캐시 키 결정**. |
| `total_price` | items 합계와 일치 권장(불일치해도 추천에는 영향 없음, 분석에만 영향). |
| `used_recommendation` | 추천 KPI(전환율). 의미있게 비율 분포. |
| `status` | `completed` 위주(또는 정의된 enum). |

### `order_items`
| 컬럼 | 합성 시 주의 |
|---|---|
| `order_id` | 반드시 `orders.id`와 매칭. |
| `menu_id` | **`menus.id`에 실재하는 ID**여야 join이 살아남음. 가짜 ID는 통계에서 제거. |
| `menu_name_snapshot` | 메뉴 이름 (메뉴 삭제 후에도 보이도록). |
| `quantity` | 1 위주, 가끔 2~3. 비현실적 큰 값(99) 회피. |
| `unit_price` | 메뉴 가격과 일치 권장. |
| `from_recommendation` | "이 라인이 추천을 통해 선택됐는가". 추천 KPI(`led_to_order` 부분 외 KPI)로 사용. |
| `selected_options_json` | **옵션 사용 통계의 입력**. 형식: `[{"option_name":"샷 추가","extra_price":500,"option_item_id":...}, ...]` (현 응답 schema 참고). |

### `recommendation_events`
| 컬럼 | 합성 시 주의 |
|---|---|
| `session_id` | sessions와 join. |
| `created_at` | sessions와 같은 날짜대. |
| `preferred_category` | 추천 카테고리별 KPI 입력. 정의된 카테고리 문자열만. |
| `recommendation_type` | (예: `popularity`, `cf`, `trend` 등) 일관 라벨. |
| `recommended_menu_id` | 메뉴 실재 ID. |
| `was_clicked` / `led_to_order` | **CTR/CVR**의 입력. shown >> clicked >> led 의 깔때기 형태로. |

### (선택) `vision_events` / `session_activity_logs`
- 대시보드 보조 통계용. 추천 엔진은 사용 안 함.
- `vision_events.age_confidence`는 추후 인구통계 신뢰도 필터에 쓰일 예정 — 합성 시 0.5~0.95 분포로.

---

## 3. 분포 / 양 검증 체크리스트

### 3-1. 시간대 (`orders.created_at` 의 `hour`)
- `_hour_to_period`가 사용하는 모든 period(예: `morning/lunch/afternoon/evening` — 정의 확인 필요)에 **각각 최소 N건 이상**의 주문이 있는지.
- 한 시간대에만 90% 몰려 있으면 다른 시간대 추천이 빈 dict가 됨.
- **권장 분포(카페 가정)**: 점심(10~13시) > 저녁(17~19시) > 오전(7~10) > 늦은 저녁(20~).
- 이전 노트: *"이전에 데이터 중에서 주문 시간대에 대한 내용이 있었는데, 그 데이터 기반해서 주문 시간 조정 필요"* — 합성 시 실제 카페 시간대 분포(예: kafka, 매장 영업 시간)에 맞춰 조정.

### 3-2. 인구통계 (`estimated_gender × estimated_age_group`)
- 정의된 모든 (성별 × 연령대) 조합에 **표본이 골고루**.
- `total_orders < 5`인 묶음은 `_get_profile_base_score`의 베이지안 가중에서 거의 global로 후퇴. 즉 추천 결과가 그 그룹과 무관해짐.
- 검증: `SELECT estimated_gender, estimated_age_group, COUNT(DISTINCT id) FROM kiosk_sessions GROUP BY 1,2;` — 빈 그룹/극단적 편향 확인.

### 3-3. 메뉴 다양성
- 한 메뉴가 전체의 50% 이상을 차지하면 항상 그것만 추천됨.
- 카테고리별로도 최소 2~3개 메뉴씩 분포.

### 3-4. 카트 연관 (co-purchase) — 한 주문 안의 다중 라인
- `order_items`에서 **한 주문 = 1개 메뉴**만 있으면 `_compute_co_purchase_stats`가 비어버림.
- 합성 시 30~50% 주문은 2개 이상의 메뉴를 포함하도록.
- 자주 같이 팔리는 페어(예: 아메리카노 + 케이크)를 의도적으로 심어 카트 추천 시그널이 만들어지도록.

### 3-5. 추천 KPI (`recommendation_events`)
- shown : clicked : led_to_order 비율은 **깔때기**여야 자연스러움.
  현실적 비율: shown 100% / clicked 10~30% / led 5~15%.
- `was_clicked=True`만 잔뜩 있으면 CTR=100%로 비현실적.

### 3-6. 시간 정합성
- `orders.created_at` 은 같은 세션의 `kiosk_sessions.started_at` 보다 같거나 늦어야 함.
- `kiosk_sessions.ended_at >= started_at` 보장.
- **모든 시각은 UTC로 저장**(코드 가정). 합성 시 KST 시각을 만들고 -9h 적용 후 저장.

### 3-7. 옵션 (`order_items.selected_options_json`)
- 모든 라인이 옵션 NULL이면 `_compute_option_usage`(애널리틱스)가 빈 결과.
- 메뉴별로 정의된 옵션 그룹 안에서 선택된 옵션을 무작위로 1~2개 채워 넣기.
- 형식 일관성: `[{"option_name": str, "extra_price": int}, ...]` — 키 이름이 다르면 옵션 사용 분석에서 제외됨.

### 3-8. 양(volume)
- 추천 캐시가 의미 있는 popularity를 만들려면 **묶음당 최소 30~50주문**.
- (성별 2 × 연령대 5 × 시간대 4 = 40개 묶음) × 30주문 = **약 1,200건의 주문 + 그 안의 라인 2,000~3,000건**이 최소 권장.

---

## 4. 합성 데이터 검증을 코드로 자동화하는 방법 (권장 SQL)

### 4-1. 시간대 분포 확인
```sql
SELECT HOUR(DATE_ADD(created_at, INTERVAL 9 HOUR)) AS kst_hour,
       COUNT(*) AS orders
  FROM orders
 GROUP BY kst_hour
 ORDER BY kst_hour;
```
- 모든 시간이 0이 아니어야 함(영업시간 제외).

### 4-2. 인구통계 매트릭스
```sql
SELECT estimated_gender, estimated_age_group, COUNT(*) AS sessions
  FROM kiosk_sessions
 GROUP BY 1, 2
 ORDER BY 1, 2;
```
- 정의된 모든 조합이 등장하고, 표본이 5건 이상.

### 4-3. 메뉴 편중 확인
```sql
SELECT m.name,
       SUM(oi.quantity) AS qty,
       ROUND(SUM(oi.quantity) / (SELECT SUM(quantity) FROM order_items) * 100, 1) AS share_pct
  FROM order_items oi JOIN menus m ON m.id = oi.menu_id
 GROUP BY m.name
 ORDER BY qty DESC;
```
- 1위 메뉴 share가 50% 미만 권장.

### 4-4. 한 주문당 라인 수
```sql
SELECT line_count, COUNT(*) AS orders
  FROM (SELECT order_id, COUNT(*) AS line_count FROM order_items GROUP BY order_id) t
 GROUP BY line_count
 ORDER BY line_count;
```
- 1줄 주문이 100%면 co-purchase 통계가 비어 있게 됨.

### 4-5. 추천 깔때기 정합성
```sql
SELECT
  SUM(CASE WHEN 1=1 THEN 1 ELSE 0 END)              AS shown,
  SUM(CASE WHEN was_clicked THEN 1 ELSE 0 END)      AS clicked,
  SUM(CASE WHEN led_to_order THEN 1 ELSE 0 END)     AS led
FROM recommendation_events;
```
- `shown ≥ clicked ≥ led` 단조 감소.

### 4-6. 외래키 무결성
```sql
-- 고아 order
SELECT COUNT(*) FROM orders o
  LEFT JOIN kiosk_sessions s ON s.id = o.session_id
 WHERE s.id IS NULL;
-- 고아 order_item
SELECT COUNT(*) FROM order_items oi
  LEFT JOIN orders o ON o.id = oi.order_id
 WHERE o.id IS NULL;
-- menu_id가 menus에 없는 라인
SELECT COUNT(*) FROM order_items oi
  LEFT JOIN menus m ON m.id = oi.menu_id
 WHERE m.id IS NULL;
```
- 모두 0이어야 추천 집계에서 행이 사라지지 않음.

### 4-7. 시간 정합성
```sql
-- 세션보다 먼저 발생한 주문
SELECT COUNT(*) FROM orders o
  JOIN kiosk_sessions s ON s.id = o.session_id
 WHERE o.created_at < s.started_at;
-- 끝나기도 전에 끝난 세션
SELECT COUNT(*) FROM kiosk_sessions WHERE ended_at IS NOT NULL AND ended_at < started_at;
```

### 4-8. 옵션 JSON 형식
```sql
-- 키 이름이 잘못된 라인
SELECT COUNT(*) FROM order_items
 WHERE selected_options_json IS NOT NULL
   AND JSON_LENGTH(selected_options_json) > 0
   AND NOT JSON_CONTAINS_PATH(selected_options_json, 'one', '$[0].option_name');
```

---

## 5. 검토 시 따로 짚을 항목 (코드 측면)

추후 코드 검토 라운드에서 다음을 본다 (지금 수정 X, 등록만):

- (a) `_hour_to_period` 정의가 무엇인지 — 현재 `recommendation_service` 내부 헬퍼. 영업시간/시간대 정의가 합성 데이터 생성기와 일치해야 함.
- (b) `_compute_profile_stats`가 모든 이력을 동일 가중치로 합산 → 트렌드 변화 반영 늦음. **CHANGE 후보**: 최근 N일 가중 또는 exponential decay.
- (c) `estimated_age_group`/`estimated_gender`가 빈 문자열인 row가 자기 그룹을 형성 → **CHANGE 후보**: 합성 데이터에서 빈 라벨 비율 통제 + 코드에서 빈 라벨 묶음을 별도 처리할지 결정.
- (d) `_get_global_popularity`가 단순 평균 → 묶음 표본 크기 가중이 아님. **CHANGE 후보**: 표본수 가중 평균.

→ 위 4개는 [02_CHANGE_REQUESTS.md](./02_CHANGE_REQUESTS.md)에 등록 가능. 사용자 결정에 따라 추가.

---

## 5-A. 기존 자산: `create_data/` 활용 평가

본 프로젝트는 이미 `create_data/` 폴더에 합성 파이프라인이 존재한다.
([README](../../create_data/README.md) · [PLAN](../../create_data/PLAN.md) · [SCHEMA](../../create_data/SCHEMA.md) · [build_dataset.py](../../create_data/build_dataset.py))

### 구성
- 원천: `raw/coffee_shop_sales.xlsx` (Kaggle).
- 매핑: `interim/menu_mapping.csv` (키워드 매칭으로 22개 카탈로그에 매핑).
- 산출: `output/{kiosk_sessions, orders, order_items}.csv` (약 59,000 세션/주문, 61,000 라인).
- `--publish-to-backend` 옵션으로 `backend/data/`에 직접 복사 → 추천 엔진이 부팅 시 그대로 로드.

### 현재 추천 엔진(인기도 + co-purchase) 기준
- ✅ 시간대/인구통계 분포는 학습에 충분.
- ✅ 부팅 즉시 반영 가능 (`--publish-to-backend`).
- ⚠️ `transaction_id` 1건 = 주문 1건 가정 → 한 주문 다중 라인 비중 검증 필요 (co-purchase 캐시가 충분히 채워지는가).
- ⚠️ `ALLOWED_SOURCE_CATEGORIES`가 음료만 통과 → 매핑 누락 양 로그 없음.

### 모델 기반 CF로 격상 시
다음이 부족하므로 별도 합성 보강이 필요:

| 부족한 것 | 영향 | 보강 방법 |
|---|---|---|
| 사용자 차원 (반복 방문) | 사용자×아이템 행렬이 1회성 | `pseudo_user_id`를 (gender, age_group, kiosk_id) 또는 user pool에서 배정 |
| `recommendation_events` | 학습 라벨 / KPI 분석 | 깔때기 비율로 합성 (shown/clicked/led) |
| `order_items.selected_options_json` | 옵션 분석/옵션 카탈로그 빈 결과 | 카테고리별 옵션 그룹 확률 선택 |
| 시간 기반 train/eval split | 평가 불가 | 마지막 N일 컷 자동화 |
| 시간대(timezone) 명시 | UTC/KST 일관성 | naive datetime → UTC 변환 후 저장 |

### 발견된 즉시 개선 후보 (코드 수정 X, 등록만)

| ID | 위치 | 내용 |
|---|---|---|
| D-01 | [build_dataset.py:295-300](../../create_data/build_dataset.py#L295-L300) | `mapping["keep"] == True` 리터럴 비교 — 외부 편집 시 문자열 케이스로 깨질 수 있음. `astype(str).str.lower() == "true"` 권장 |
| D-02 | [build_dataset.py:333-336](../../create_data/build_dataset.py#L333-L336) | naive datetime 저장 → 추천 엔진의 UTC 가정과 불일치 가능. 명시적 `tz_localize` 또는 UTC 변환 |
| D-03 | [build_dataset.py:351-373](../../create_data/build_dataset.py#L351-L373) | session 1:1 transaction → 반복 사용자 패턴 없음. 모델 기반 CF의 결정적 한계 |
| D-04 | [build_dataset.py:38](../../create_data/build_dataset.py#L38) | 매핑 누락 카테고리/메뉴 통계 로그 부재. 손실량 추적 어려움 |
| D-05 | (미존재) `output/recommendation_events.csv` | 분석 KPI / 학습 라벨에 모두 필요 |
| D-06 | (미존재) `order_items.selected_options_json` | 옵션 사용 분석 빈 결과 |
| D-07 | [build_dataset.py:424-466](../../create_data/build_dataset.py#L424-L466) | `validate_outputs`가 시간 정합성·매핑 누락 비율·co-purchase 충분성 미커버 |

→ D-01 ~ D-07은 [02_CHANGE_REQUESTS.md](./02_CHANGE_REQUESTS.md)의 신규 항목 후보.

---

## 6. 합성 데이터 생성 시 권장 절차

1. **메뉴/카테고리 먼저 시드** (운영과 동일 데이터셋).
2. **세션 생성**:
   - 영업일 N일 × 일별 세션 수 M개.
   - 시각은 KST 영업시간 분포에 맞춰 샘플링 → UTC로 변환 저장.
   - 성별/연령대는 매트릭스 균형 잡히게 stratified sampling.
3. **세션마다 주문 1건 (또는 일부는 0건/2건)**.
   - 주문 시각은 세션 시작 +1~5분.
4. **주문마다 1~3개 라인**. 30~50%는 2개 이상.
5. **자주 같이 팔리는 페어** 의도적으로 주입.
6. **`recommendation_events`** 는 세션 1건당 0~3건 분포로 생성, shown→clicked→led 깔때기 비율 준수.
7. 생성 직후 위 §4 SQL을 모두 돌려 빨간불 확인.

---

## 7. 결론 / TL;DR

- `_compute_profile_stats`는 **데이터 분포가 곧 추천 결과**를 만든다.
- 합성 데이터는 **시간대/인구통계/메뉴/주문 라인 수/추천 깔때기** 5축에서 모두 균형이 잡혀야 한다.
- 외래키·시각 정합성·옵션 JSON 키 같은 **포맷 검증**을 SQL 한 페이지로 자동화하면 데이터 교체 시마다 빠르게 sanity check 가능.
- 이전 시간대 분포 이슈처럼, 데이터 생성기는 **실제 카페 영업시간**과 **현재 코드의 `_hour_to_period` 정의**를 동시에 맞춰야 한다.
