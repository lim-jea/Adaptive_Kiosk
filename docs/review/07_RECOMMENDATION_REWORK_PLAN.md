# 추천 시스템 재정비 계획 — 통계 기반 + 합성 데이터 채택

> 결정 근거: [노트북 08 검증 결과](../../create_data/output/08_evaluate_lift_and_ablation.ipynb) — FM/ALS/I2V 학습 모델이 POP 대비 +0.7%p, 인구·컨텍스트 셔플에 거의 영향 없음. WEAK 1/5.
> 결론: 모델 채택 안 함. **backend의 기존 통계 추천 엔진을 그대로 두고, 입력 데이터만 우리 합성 데이터로 교체**.
> 이 작업은 노트북 없이 backend 수정 + 데이터 복사로 완료.

---

## 0. 작업 원칙

1. **API 입출력 불변** ([00_REVIEW_PLAN.md](./00_REVIEW_PLAN.md)) — 추천 응답 스키마 변경 금지.
2. **통계 추천 엔진 코어 로직은 유지** — `_compute_profile_stats`, `_compute_co_purchase_stats`, `_get_profile_recommendations` 등은 그대로.
3. **입력 데이터·메뉴 매핑만 교체** — `backend/data/` CSV + `seed_menu`.
4. **모델 학습 산출물은 보존만** — 추후 데이터 누적 시 재활용 가능. backend에 통합은 안 함.

---

## 1. 현황 진단

### 1-1. backend 추천 엔진 (이미 통계 기반)
- 위치: [backend/services/recommendation_service.py](../../backend/services/recommendation_service.py).
- 입력: `backend/data/{kiosk_sessions,orders,order_items}.csv`.
- 핵심 통계:
  - `_compute_profile_stats` — (gender × age_group × period × menu) 인기도.
  - `_compute_co_purchase_stats` — item × item 동시구매.
  - `_calculate_hourly_weights` — 시간대별 인기도 가중.
  - `_build_trend_weight` — 외부 트렌드(Naver DataLab) 곱셈.
  - `_get_profile_base_score` — 베이지안 평균(`n/(n+20)`).

### 1-2. 현재 backend 데이터 한계
- `backend/data/kiosk_sessions.csv` 등 — Maven Coffee Shop Sales 기반으로 생성된 기존 데이터.
- 다중 라인 0%, 메뉴 4개로 축소(82% 손실), 인구 × 메뉴 상관 거의 없음.
- 우리가 진단한 [CHANGE-009/010/011](./02_CHANGE_REQUESTS.md) 모두 해당.

### 1-3. 우리가 만든 자산 (Phase 1 산출)
- Drive `output/`:
  - `kiosk_sessions.csv` (48,632 세션, 인구통계 OpenSurvey prior 적용).
  - `kiosk_orders.csv` (48,632 주문).
  - `kiosk_order_items.csv` (68,942 라인, 다중 라인 40%).
- 메뉴: `kr_synthetic/rec_items.csv` (한국 카페 30개, 우리 22 카탈로그와 거의 1:1 매핑).

### 1-4. 모델 산출물 (보존만, backend 통합 X)
- `output/artifacts/`:
  - `item2vec_kiosk_embeddings.npy`, `kiosk_index.json`
  - `fm_kiosk_weights.npz`, `fm_feature_encoder.pkl`
  - `als_user_factors.npy`, `als_item_factors.npy` 등
- 보존 이유: 캡스톤 보고서 비교 자료 + 미래 데이터 누적 시 재활용.

---

## 2. 변경 항목 분류

### 카테고리 ①: **데이터 교체 (코드 변경 X)**

| # | 파일 | 변경 |
|---|---|---|
| D-1 | `backend/data/kiosk_sessions.csv` | **교체**: 합성 sessions를 backend 스키마로 변환해 덮어씀 |
| D-2 | `backend/data/orders.csv` | **교체**: 합성 orders 변환 후 덮어씀 |
| D-3 | `backend/data/order_items.csv` | **교체**: 합성 order_items 변환 후 덮어씀 |

**변환 필요한 컬럼**:

| 합성 데이터 (Phase 1) | backend 기대 컬럼 | 변환 |
|---|---|---|
| `sex` (남/여) | `estimated_gender` (M/F) | 매핑 dict |
| `age_10` (20대/30대/...) | `estimated_age_group` (그대로) | 그대로 |
| `item_id` (`I001`~`I030` 문자열) | `menu_id` (정수 1~30) | int 변환 + `seed_menu` ID와 정합 |
| `is_weekend`, `is_promo` 등 | (backend는 사용 안 함) | 무시 |
| (없음) | `kiosk_id` | 1로 채움 |
| (없음) | `from_recommendation` | False로 채움 (운영 누적 후 의미 생김) |

### 카테고리 ②: **메뉴 시드 정합화**

| # | 파일 | 변경 |
|---|---|---|
| M-1 | `backend/scripts/seed_menu.py` | **수정**: 우리 22개 카탈로그 → rec_items 30개로 확장 또는 매핑 테이블 도입 |
| M-2 | `backend/model.py` `Menu` 테이블 | **변경 없음** (스키마 호환) |
| M-3 | (신규) `backend/data/menu_master.json` | **추가 (선택)**: rec_items 메타(caffeine_mg/sugar_g/calorie/base_price 등)를 seed_menu 보강용 |

**핵심 결정**: 운영 카탈로그를 22개 유지할지, 30개로 확장할지.

- **옵션 A (유지 22개)**: rec_items 30개 → 22개로 축소 매핑. 우리 카탈로그 변경 없음. 합성 데이터 일부 손실(8개 메뉴).
- **옵션 B (확장 30개)**: backend `seed_menu`를 rec_items 30개로 교체. 카탈로그 변경, 프런트 UI 영향 가능.
- **권장 옵션 A**: 변경 범위 최소.

### 카테고리 ③: **backend 코드 미세 보강**

| # | 파일 / 함수 | 변경 |
|---|---|---|
| C-1 | `recommendation_service._compute_profile_stats` | **변경 없음** (이미 충분) |
| C-2 | `recommendation_service._compute_co_purchase_stats` | **변경 없음** |
| C-3 | `recommendation_service._normalize_frames` | **확인만**: 합성 데이터 컬럼이 정상 정규화되는지 검증 |
| C-4 | `recommendation_service.load_data` | **변경 없음** |
| C-5 | `recommendation_service._hour_to_period` | **선택 변경**: 노트북 03의 `period_day` 라벨(주말/평일×시간대)과 정합 검토 — 단 운영에선 hour만 받으니 그대로 둬도 됨 |
| C-6 | `main.py` lifespan `seed_menu_data` 호출 | **확인**: 옵션 A일 경우 변경 없음. 옵션 B면 `seed_menu`도 갱신 필요 |

### 카테고리 ④: **새로 만들어야 할 부분**

| # | 파일 | 역할 |
|---|---|---|
| N-1 | `backend/scripts/sync_synthetic_data.py` (신규) | **합성 데이터 → backend 데이터 컬럼 매핑·복사 스크립트**. 실행 한 번이면 backend/data 갱신. (또는 `create_data/` 안에 두는 것도 가능) |
| N-2 | (선택) `backend/data/menu_id_mapping.json` | rec_items의 `I001` → seed_menu의 `menu_id` 매핑 영구 저장 |
| N-3 | (선택) `docs/recommendation/STATISTICAL_BASELINE.md` | 보고서용: "왜 모델 학습을 안 채택했는가 + 통계 추천 채택 근거 + 노트북 08 검증 결과 인용" |

### 카테고리 ⑤: **지워야 할 부분 (주의 — 보존 권장)**

| # | 항목 | 결정 |
|---|---|---|
| X-1 | 노트북 04~08 산출 artifacts (`item2vec_*`, `fm_*`, `als_*`) | **삭제 X — 보존**. Drive에 남겨둠. 캡스톤 보고서 자료. |
| X-2 | 노트북 06의 `recommendation_artifacts/` 패키지 | **삭제 X — 보존**. 미래 backend 통합용. |
| X-3 | backend 기존 추천 모델 통합 인터페이스 자리 (`item_embedding_service.py`, `context_fm_service.py`) | **만들지 않음**. 이전 계획에 있었으나 채택 안 됨. |
| X-4 | [02_CHANGE_REQUESTS.md](./02_CHANGE_REQUESTS.md) CHANGE-014/015 | **상태 변경**: "보류" → "기각 (통계 추천 채택)" |

### 카테고리 ⑥: **검증 / 운영 점검**

| # | 항목 | 방법 |
|---|---|---|
| V-1 | 합성 데이터 적재 후 backend 부팅 | 로그에 `Recommendation CSV loaded: 48632 sessions, 48632 orders, 68942 items` 확인 |
| V-2 | `_compute_profile_stats` 정상 산출 | 로그에 `profile_keys` count + cache hit |
| V-3 | API 응답 정합성 | `/api/v1/recommendations/...` 호출 → 응답 스키마 그대로 |
| V-4 | admin 대시보드 정상 동작 | 노트북 06의 ADMIN 검토 결과대로 정상 |
| V-5 | 메뉴 ID 정합성 | 추천 결과의 menu_id가 backend `menus` 테이블에 실제 존재 |

---

## 3. 작업 순서 (단계별)

### Phase A — 사전 준비 (10분)
1. **현재 backend 상태 백업**:
   - `backend/data/{kiosk_sessions,orders,order_items}.csv` → `backend/data/_legacy/`로 이동 (롤백용).
2. **메뉴 매핑 테이블 결정**:
   - 옵션 A: rec_items 30 → backend 22 매핑 dict 작성 (`menu_id_mapping.json`).
   - 옵션 B: seed_menu 갱신 (변경 폭 큼).
   - **권장 옵션 A**.

### Phase B — 변환 스크립트 작성 (`sync_synthetic_data.py`) (30분)
- 입력: Phase 1 산출 합성 CSV (Drive에서 로컬 복사 후 사용).
- 출력: `backend/data/{kiosk_sessions,orders,order_items}.csv` 덮어쓰기.
- 처리:
  1. sex → estimated_gender (남→F가 아니라 한국어 그대로 유지할 가능성 → backend 표기 정합 검토).
  2. age_10 → estimated_age_group 그대로.
  3. item_id → menu_id 정수 변환 (매핑 dict 적용).
  4. kiosk_id=1 채움.
  5. from_recommendation=False 채움.

### Phase C — backend 검증 (10분)
- backend 재시작 → 로그 확인.
- swagger `/docs`에서 추천 API 호출 → 응답 정상.
- admin 대시보드 → 통계 카드/그래프 정상.

### Phase D — 정리 (10분)
- [02_CHANGE_REQUESTS.md](./02_CHANGE_REQUESTS.md): CHANGE-009/010/011/014/015 상태 갱신.
- [00_REVIEW_PLAN.md](./00_REVIEW_PLAN.md) Phase 4 — backend 통합 항목 정리.
- 보고서용 한 줄: "복잡한 모델 학습 비교 후 검증으로 통계 추천 동등성 입증, backend 단순 통계 추천에 합성 데이터 적용".

---

## 4. 메뉴 매핑 테이블 초안 (옵션 A — rec_items 30개 → backend 22개)

backend `seed_menu`(추정 22개) ↔ rec_items.csv(한국식 30개) 매핑 예시:

```
rec_items                  →  backend menu_name           note
I001 에스프레소               →  에스프레소
I002 아메리카노(HOT)         →  따뜻한 아메리카노
I003 아메리카노(ICE)         →  아이스 아메리카노
I004 콜드브루                →  콜드브루
I005 드립커피                →  드립 커피
I006 카페라떼(HOT)           →  따뜻한 카페라떼
I007 카페라떼(ICE)           →  아이스 카페라떼
I008 카푸치노                →  카푸치노
I009 달콤한커피(HOT)         →  바닐라 라떼          (가장 가까운 매핑)
I010 달콤한커피(ICE)         →  카라멜 마끼아또      (가장 가까운 매핑)
I011 콜드브루라떼            →  콜드브루 라떼
I012 프라푸치노              →  프라푸치노
I013 블렌디드                →  말차 프라페          (가장 가까운 매핑)
I014 아포가토                →  (drop)              22개에 없음
I015 말차라떼                →  녹차 라떼
I016 밀크티(HOT)             →  (drop)              22개에 없음
I017 밀크티(ICE)             →  (drop)
I018 그린티라떼              →  녹차 라떼            (I015와 합침)
I019 얼그레이                →  캐모마일 티          (가장 가까운 매핑)
I020 캐모마일                →  캐모마일 티
I021 페퍼민트                →  (drop)
I022 루이보스                →  (drop)
I023 망고스무디              →  딸기 스무디          (가장 가까운 매핑)
I024 딸기스무디              →  딸기 스무디
I025 그린티프라페            →  말차 프라페          (I013와 합침)
I026 과일티스무디            →  복숭아 아이스티      (가장 가까운 매핑)
I027 레몬에이드              →  레몬에이드
I028 자몽에이드              →  자몽에이드
I029 오렌지주스              →  오렌지 주스
I030 청포도에이드            →  자몽 허니 블랙 티    (가장 가까운 매핑)
```

**검증 필요**: 위 매핑이 맞는지 사용자 확인. 혹은 `backend/scripts/seed_menu.py`를 열어 실제 seed 메뉴 22개를 정확히 확인 후 확정.

---

## 5. 스크립트 인터페이스 명세 (Phase B 작업물)

### `backend/scripts/sync_synthetic_data.py`

```bash
# 사용법 (실행 한 번이면 backend/data/ 갱신 끝)
python -m scripts.sync_synthetic_data \
    --source <Drive에서 로컬로 복사한 합성 데이터 폴더> \
    --target backend/data \
    --menu-mapping backend/data/menu_id_mapping.json
```

### 동작
1. `kiosk_sessions.csv` 로드 → 컬럼 정규화 → backend/data/kiosk_sessions.csv 덮어씀.
2. `kiosk_orders.csv` 로드 → 정규화 → backend/data/orders.csv.
3. `kiosk_order_items.csv` 로드 → menu_id 매핑 적용 → backend/data/order_items.csv.
4. 매핑에서 drop된 메뉴(I014/I016/I017/I021/I022)에 해당하는 라인 제거 + 해당 주문이 빈 주문이면 주문도 제거.
5. 통계 출력: 적재된 행 수, drop된 비율, 메뉴별 분포.

### 안전장치
- backend/data/_legacy/ 자동 백업.
- dry-run 옵션 (`--dry-run`): 변경 없이 변환 결과만 출력.
- 검증 옵션 (`--verify-only`): 적재 후 (gender × age × period) 묶음 분포 출력.

---

## 6. 변경 영향 요약

| 영역 | 변경 |
|---|---|
| backend 추천 엔진 코드 | **변경 없음** |
| backend 추천 응답 스키마 | **변경 없음** |
| backend 데이터 (3개 CSV) | 합성 데이터로 교체 |
| backend 메뉴 시드 | 변경 없음 (옵션 A) |
| 프런트엔드 | **영향 없음** |
| admin 페이지 | 통계가 새 데이터 기준으로 갱신됨 (자연스러운 동작) |
| 보존 자산 | Drive `output/` 노트북·artifacts 모두 보존 |

---

## 7. 작업 후 즉시 확인할 것

1. `backend` 재기동 시 `Recommendation CSV loaded: 48632 sessions, 48632 orders, 68942 items` 로그 확인.
2. `recommendation_engine.precompute_all_stats()` 실행 후 `profile_keys` 가 (sex × age × 5 period × menu) 조합으로 풍부한지 (수십~수백 키).
3. `/api/v1/recommendations/...` API 호출 시 응답에 `final_score / mode / reasoning` 등 기존 필드 그대로.
4. admin "분석" 페이지의 Funnel/Heatmap 정상 렌더링.

---

## 8. 결정해야 할 항목 (작업 시작 전)

1. **메뉴 매핑 정책**: 옵션 A (22개 유지, drop 5개) vs 옵션 B (30개 확장).
2. **변환 스크립트 위치**: `backend/scripts/` 안 vs `create_data/` 안.
3. **성별 라벨**: backend가 한국어 "남/여" 받는지 영문 "M/F" 받는지 — backend `model.py` `KioskSession.estimated_gender = String(10)`이라 어느 쪽이든 가능, 일관성만 잡으면 됨.
4. **`from_recommendation` 초기값**: `False`로 시작 (운영 누적 후 진짜 값) vs OpenSurvey 기반 합성 시 일부에 `True` 부여.
5. **drop된 합성 메뉴**(아포가토·밀크티·페퍼민트·루이보스): 매핑 안 하고 drop 확정?

---

## 9. 일정

| Phase | 시간 |
|---|---|
| A. 사전 준비 + 매핑 결정 | 20분 |
| B. 변환 스크립트 작성 | 30분 |
| C. backend 검증 | 15분 |
| D. 정리 + 문서 업데이트 | 15분 |
| **총** | **약 1시간 20분** |

---

## 10. 다음 행동

위 §8의 5개 결정 사항을 알려주시면 즉시 Phase A부터 작업 시작합니다.

**제 권장 기본값**:
1. 옵션 A (22개 유지).
2. `create_data/` 안에 변환 스크립트 (`sync_to_backend.py`) — backend 폴더 오염 최소화.
3. 한국어 "남/여" 그대로 유지 (변환 비용 0).
4. `from_recommendation = False` 일괄.
5. drop 5개 확정 + 보고서에 기록.

이 기본값대로 진행해도 되는지 / 일부 변경하실지 알려주세요.
