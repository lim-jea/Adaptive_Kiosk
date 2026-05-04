# 작업 로그 — 2026-05-05 (추천 시스템 데이터 결정)

> 본 문서는 2026-05-05 단일 일자에 진행된 작업의 **순차 기록**이다. 결정 사항은 [02_CHANGE_REQUESTS.md](02_CHANGE_REQUESTS.md), 전체 재설계는 [07_RECOMMENDATION_REWORK_PLAN.md](07_RECOMMENDATION_REWORK_PLAN.md), 다음 단계는 [09_BACKEND_INTEGRATION_PLAN.md](09_BACKEND_INTEGRATION_PLAN.md).

## 0. 출발점

- 직전까지 모델 기반 추천(Item2Vec, FM, LightFM/ALS)을 시도해 온 상태.
- LightFM 은 Python 3.12 Cython 빌드 실패. ALS 로 대체했으나 통계 baseline(POP) 대비 lift 미미.
- `notebooks/08_evaluate_lift_and_ablation.ipynb` 의 ablation 결과 → **WEAK 판정 (1/5)**, 즉 모델이 통계 기반 baseline 을 의미 있게 넘지 못함.
- 결론: 학습형 모델 도입 보류, 통계 기반 엔진 + **양질의 합성 데이터** 노선으로 선회.

## 1. 격리 테스트 환경 구축

backend 코드를 손대지 않고 합성 데이터의 효과만 검증하기 위한 sandbox 를 만든다.

생성 위치: `create_data/recommendation_test/`

| 파일 | 역할 |
|---|---|
| `recommendation_service_copy.py` | backend `services/recommendation_service.py` 의 단순 복사본. 본 폴더에선 **편집 금지** |
| `menu_id_mapping.json` | rec_items 30개 → backend seed_menu 22개 매핑 (5개 drop: 아포가토·밀크티 HOT/ICE·페퍼민트·루이보스 — backend 카탈로그 부재) |
| `sync_synthetic_data.py` | 합성 CSV → backend 스키마 변환 (sessions/orders/order_items) |
| `run_test.py` | engine 격리 실행 + 다중 데이터셋 비교 리포트 |

격리 실행 시 import 실패 방지를 위해 `sqlalchemy`, `model`, `services.trend_service` 의 stub 을 `sys.modules` 에 주입.

profile_stats / co_purchase_stats 는 backend 부팅 시 비동기로 채워지므로, sandbox 에선 `make_engine()` 내부에서 동기 호출로 강제 채움:

```python
engine._profile_stats     = engine._compute_profile_stats()
engine._co_purchase_stats = engine._compute_co_purchase_stats()
engine._use_cache = True
```

## 2. 1차 비교 — legacy vs v1 합성

### 2-1. 데이터 출처
- **legacy**: backend/data 의 기존 CSV (Maven Coffee Shop Sales 가공). 2,000 세션 / 17.5k 라인.
- **v1 합성**: 이전에 OpenSurvey prior 기반으로 Drive(`output/`)에 생성해 둔 데이터 → `source_synthetic/` → `data/` 로 변환. 45,709 세션 / 60.2k 라인.

### 2-2. 1차 결과 — 통계 풍부도는 우상향, 그러나 추천 결과 의심

| 항목 | legacy | v1 | 평가 |
|---|---|---|---|
| sessions | 2,000 | 45,709 | v1 ×23 |
| profile_keys | 40 | 40 | 동일 |
| avg_total_orders/key | 293 | 1,009 | v1 ×3.4 (더 robust) |
| co_purchase_menus | 21 | 22 | v1 우위 |

샘플 추천 4 컨텍스트 모두 **`말차 프라페 + 따아 + 아아 + 복숭아ICE + 녹차라떼`** 에 수렴. 사용자가 "다 말차 프라페가 나오는데 이게 맞나" 라고 의심.

## 3. 2차 분석 — 의심의 정량 검증

사용자 요청에 따라 “계산이 맞는지, 변경할 가치가 있는지” 정량 검토.

### 3-1. 엔진은 정상

같은 `_compute_profile_stats` / `_compute_co_purchase_stats` 코드가 두 데이터에 동일하게 적용. **버그 아님.**

### 3-2. 데이터 분포 진단

| 지표 | legacy | v1 | 의미 |
|---|---|---|---|
| HHI (메뉴 집중도) | 0.0579 | 0.0565 | 둘 다 균등(0.0455)에 근접 — 전체 분포는 OK |
| top5 누적 점유율 | 39.1% | 40.9% | 비슷 |
| **단일 메뉴 max share** | 9.05% (아아) | **9.84% (말차)** | 22종 카페에서 1메뉴 ~10% 는 비현실적 |
| **context-level unique top1** | **7/40** | **3/40** | v1 의 컨텍스트 분리력이 절반 이하 |
| top1 분포 | 따아22, 아아11, 카라멜2, 바닐라2, 자몽에이드1, 레몬에이드1, 콜드브루1 | **말차20, 따아16, 복숭아ICE4** | v1 은 사실상 2종 메뉴가 모든 컨텍스트 점령 |

→ **v1 합성 데이터는 시간대(period) 차원의 메뉴 분리 prior 가 약했다.** 인구(성별·연령) prior 만으로는 같은 사람이 시간대 무관하게 같은 메뉴를 고르는 결과로 수렴.

### 3-3. 결론

- 엔진은 올바름.
- v1 합성 데이터는 통계량 풍부하지만 **컨텍스트 분리력이 legacy 보다 떨어짐.**
- 현 상태로 backend 반영 시 모드 A 추천이 거의 항상 "말차 프라페 / 따아" 로 고정될 것. **반영 보류 결정.**

## 4. v2 합성 데이터 생성기 작성

위치: `create_data/recommendation_test/generate_synth_v2.py`

### 4-1. 설계 변경점

1. **명시적 prior 분리**
   - `PERIOD_ADJ`: morning/lunch/afternoon/dinner/late × 메뉴 logit 보정
     - morning → 따아·아아·콜드브루·드립커피↑, 디저트/스무디↓
     - afternoon → 프라푸치노·스무디·에이드↑, 정통커피↓
     - dinner/late → 캐모마일·자몽블랙·복숭아아이스티(디카페인)↑, 카페인↓
   - `GENDER_AGE_ADJ`: (성별, 연령) × 메뉴 logit 보정
     - 여 20대 → 단맛 라떼/스무디/에이드↑
     - 남 50대 → 아메리카노·드립커피·에스프레소↑

2. **Iterative softmax cap (max_share=0.06)**
   - softmax 후 어떤 메뉴도 6% 를 넘지 못하게 반복 재분배.
   - v1 의 단일-메뉴 도배(말차 9.84%) 구조적 차단.

3. **컨텍스트별 logit 캐시 + 노이즈**
   - 동일 (gender, age, period) 안에선 같은 logit 사용 (인간 선호의 안정성 가정)
   - 작은 가우시안 노이즈로 변동성 부여

4. **다중 라인 주문**
   - `n_items = 1 + Poisson(0.7)` clip 1~3 → 평균 items/order ≈ 1.66 (v1 의 1.32 대비)
   - co-purchase 학습 강화

5. **22 메뉴 직접 사용**
   - rec_items 30 ID 중 21 매핑 + 5 drop 의 낭비 구조 제거
   - 22 메뉴에 1:1 매칭되는 22 item_id 만 사용

### 4-2. v2 검증 결과

| 항목 | legacy | v1 | **v2** | 평가 |
|---|---|---|---|---|
| sessions | 2,000 | 45,709 | 50,000 | OK |
| items/order | 1.50 | 1.32 | **1.66** | ✅ |
| HHI | 0.0579 | 0.0565 | **0.0457** | 거의 균등 |
| 단일 메뉴 max share | 9.05% | 9.84% | **5.17%** (복숭아ICE) | ✅ cap 작동 |
| context unique top1 | 7/40 | 3/40 | **18/40** | ✅ 컨텍스트 분리 |
| co_purchase pairs/menu | 18.67 | 20.27 | **21.0** | ✅ |

샘플 추천 (말차 도배 해소 확인):
- 여 20대 9h: 복숭아ICE / 따아 / 콜드브루 / 카라멜 / 바닐라라떼
- 남 30대 19h: **캐모마일 / 자몽블랙 / 따라떼 / 콜드브루라떼 / 카푸치노** (디카페인 prior 작동)
- 남 50대 8h: **에스프레소 / 복숭아ICE / 자몽블랙 / 아아 / 드립커피** (성인 정통 커피 prior 작동)

→ **v2 모든 점검 항목 통과.** 프라이어 의도가 추천 결과에 그대로 반영됨.

## 5. run_test.py — 다중 데이터셋 비교 확장

기존 2-way (legacy + synth) → N-way (`legacy + synth + synth2`) 로 확장.

```powershell
python run_test.py --compare                       # 모든 데이터셋
python run_test.py --compare-sets legacy synth2    # 부분 비교
```

`compare_multi()` 가 컨텍스트 키 합집합 기준으로 표를 자동 정렬.

## 6. 파일 구조 정리 (오늘 함께 진행)

`create_data/_archive/` 폴더 생성 — **삭제 대신 보존** + 인덱스(`INDEX.md`).

이동된 항목 카테고리:
| 카테고리 | 내용 | 사유 |
|---|---|---|
| `_archive/rejected_notebooks/` | 04~08 모델 학습/평가 노트북 (notebooks/) | 모델 효과 미확인, WEAK 판정 |
| `_archive/rejected_artifacts/` | 04~08 출력 노트북 + artifacts/ + recommendation_artifacts/ | 학습 산출 미사용 |
| `_archive/early_cf_attempts/` | 02~04 user/item-based CF 노트북 + CF+content 실험 | 외부 데이터 mismatch + kiosk user-id 부재 |
| `_archive/external_datasets/` | bread_basket / Restaurant_Orders / coffee_sales / starbucks 등 | 도메인 mismatch |

정리 후 `create_data/` 활성 구조:

```
create_data/
├── PLAN.md / README.md / SCHEMA.md           ← 메타
├── build_dataset.py                          ← 합성 데이터 메인 빌더
├── notebooks/                                ← 활성 (01 EDA, 02 OpenSurvey, 03 build & validate)
├── raw/                                      ← 원본 prior (kr_synthetic/)
├── output/                                   ← 03 노트북 산출 (kiosk_*.csv)
├── interim/                                  ← 중간 산출
├── recommendation_test/                      ← 오늘의 핵심 산출 (격리 테스트 + v2 생성기)
└── _archive/                                 ← 거부된 시도 보존 (INDEX.md)
```

## 7. 새/업데이트된 문서

| 문서 | 용도 |
|---|---|
| `create_data/_archive/INDEX.md` | 보존된 항목 인덱스 |
| `create_data/recommendation_test/README.md` | v2 프로세스 반영 업데이트 |
| `docs/review/08_TODAY_WORKLOG_2026-05-05.md` | 본 문서 |
| `docs/review/09_BACKEND_INTEGRATION_PLAN.md` | v2 → backend 적용 가이드 |

## 8. 추가 정리 (오늘 후반)

### 8-1. v2 재생성 후 검증 (period 경계 backend 와 정렬 후)

`hour_to_period` 와 `PERIOD_ADJ` 키를 backend 의 5-period (`morning/lunch/afternoon/evening/night`) 에 맞춰 generator 수정 → `--seed 42` 로 재생성 → 4 컨텍스트 모두 의도 그대로 유지됨을 재확인.

| context | period | 기대 효과 (prior) | 재생성 후 실제 추천 |
|---|---|---|---|
| 여 20대 9h | morning | 정통커피↑ + 단맛 약간 | 콜드브루 / 따아 / 카라멜 / 드립 / 레몬에이드 |
| 여 30대 13h | lunch | 라떼류 prior | 콜드브루라떼 / 따라떼 / 아라떼 / 아아 / 프라푸치노 |
| 남 30대 19h | **evening** | **디카페인 티↑** | 따라떼 / **캐모마일 / 자몽블랙 / 복숭아ICE** / 콜드브루라떼 |
| 남 50대 8h | morning | 50대남 정통 커피 | 드립커피 / 에스프레소 / 콜드브루 / 자몽블랙 / 아아 |

→ 말차 도배 없음, prior 의도 명확히 반영. 모든 정량 지표(HHI, max share, unique top1) 도 통과.

### 8-2. 추가 archive 이동 + repo 밖 분리

(1) 거부/대체된 자료들을 우선 `create_data/_archive/` 로 모음:

| 항목 | 사유 |
|---|---|
| `create_data/output/{kiosk_sessions,orders,order_items}.csv` (59k rows) | backend 미반영 v0 합성. v1/v2 로 대체됨 |
| `create_data/raw/coffee_shop_sales.xlsx` | Maven 원본. v2 채택으로 deprecated |
| `create_data/build_dataset.py` + `interim/menu_mapping.csv` | 어떤 활성 노트북도 import 안 함 |
| `__pycache__/` (양 폴더) | 자동 재생성 캐시 → 삭제 |

(2) 그 후 git 추적 부담을 줄이기 위해 **`create_data/_archive/` 통째를 repo 외부**로 이동:

```
c:/Users/jeayy/Desktop/26년도 산학협력캡스톤/Adaptive_Kiosk/create_data/_archive/
  → c:/Users/jeayy/Desktop/26년도 산학협력캡스톤/research_archive/
```

(79 files / 56.2 MB) — 외부 라이선스 데이터(Starbucks transcript 27MB 등) + 거부된 모델 산출.
보존은 유지하되 git 추적 외부에 두어 repo 를 가볍게 유지한다.

이에 따라:
- `.gitignore` 의 임시 차단 블록 모두 **원상복구** (이번 변경 이전 상태로).
- `docs/review/10_GITIGNORE_POLICY.md` (임시 정책 문서) 삭제.
- `create_data/README.md` 의 _archive 언급은 `../research_archive/` 참조로 갱신.

git 에 commit 될 대상은 다음으로 좁혀진다 — **합성 데이터 구축 + v1/v2 격리 검증 코드 + 관련 문서**:

- `create_data/notebooks/` (01·02·03 활성 EDA/합성 노트북)
- `create_data/raw/kr_synthetic/` (prior 입력)
- `create_data/output/0{2,3} notebook result/` (활성 노트북 실행본)
- `create_data/recommendation_test/` (전체 — 코드 + v1·v2 산출 + 비교 리포트)
- `docs/review/*.md` (검토 로그 + 08·09)
- 기타 한국어 docs 3개

## 9. 다음 회차 시작점

1. (선택) v2 안정성 점검: `--seed` 를 바꿔 재생성 후 같은 점검 항목이 모두 만족되는지 확인.
2. (선택) v3 로 prior 미세 조정: 단맛/디카페인 차원을 더 세분화.
3. (확정) 이상 없으면 `09_BACKEND_INTEGRATION_PLAN.md` 의 절차로 backend/data 에 v2 반영.
4. 캡스톤 보고서: 모델형 거부(WEAK) → 통계+합성 데이터 채택 의사결정 트리 정리. 인용 자료는 `_archive/INDEX.md` §7 참조.
