# 카페 추천 시스템 — 데이터·모델 작업 계획 (FINAL)

> 본 계획은 OpenSurvey 기반 자체 합성 데이터를 우선 생성한 뒤, 그 위에서 두 모델을 병렬 학습하는 방향으로 정리됨.
> 이전 계획·논의 통합본. 이 문서가 작업의 단일 source of truth.

---

## 0. 결정 요약

| 항목 | 결정 |
|---|---|
| 모델 구조 | **Item2Vec + FM 병렬** (역할 분리) |
| 통합 흐름 (C-3) | 카트 비었을 때 FM, 채워지면 두 모델 결합 |
| 합성 데이터 | **OpenSurvey 분포 + 외부 reference 검증 위에 자체 합성** (Phase 1) |
| 학습 데이터 | Phase 1 자체 합성 + Bread Basket + rec_interactions(비교) (Phase 2) |
| 평가 | HitRate@K / NDCG@K / Coverage |
| API 영향 | **응답 스키마 불변** — 점수 분해 필드만 추가 |

---

## 1. 자산 (확정)

### 학습/검증에 사용
| 데이터 | 역할 |
|---|---|
| `bread basket.csv` | Item2Vec 학습 (다중 라인 영수증) |
| `opensurvey_cafe_2025_synthetic.csv` | 인구통계 × 메뉴/시간 prior 추출 |
| `rec_users.csv` | 사용자 마스터 (OpenSurvey와 user_id 일치) |
| `rec_items.csv` | 한국 카페 메뉴 메타 (caffeine/calorie/price) |
| `rec_calendar.csv` | 휴일·시험·프로모 라벨 |
| `rec_weather_log.csv` | 시간별 기상 |
| `rec_interactions.csv` | FM 학습 비교/보강 데이터 |

### Reference로만 사용
| 데이터 | 용도 |
|---|---|
| `Coffee Sales Dataset` | 카페 시간대 분포 reference (외부 검증) |
| `Starbucks Customer Data` | 글로벌 인구통계 비교 (보고서 부록) |
| 자료조사 PDF (NIQ Korea, Simon-Kucher, 학술논문) | 합성 가설 효과 크기 reference |

### 폐기
- `Daily Coffee Transactions` (Coffee Sales와 중복)
- `archive (2)/` (Bread Basket과 중복)
- `Restaurant_Orders/` (음료 0개)
- `GACTT` (미국 시음, 본 모델과 무관)
- `rec_ml_features.csv` (자체 인코딩 사용 — 미사용)
- `rec_stores.csv` (매장 컨텍스트는 1순위 아님 — 보류)

---

## 2. Phase 구조 (압축 6 노트북)

```
Phase 1 — OpenSurvey 기반 자체 합성 (검증 포함)
    노트북 02 → 03
                ↓
Phase 2 — 모델 학습 (병렬)
    노트북 04 (Item2Vec)  ‖  노트북 05 (FM)
                ↓
Phase 3+4 — 평가·결합·backend export
    노트북 06
```

### 노트북 매핑

| 노트북 | Phase | 입력 | 출력 |
|---|---|---|---|
| `01_eda_bread_basket.ipynb` (완료) | 사전 EDA | bread basket.csv | `output/transactions_clean.csv`, `output/menus_meta.csv` |
| `02_opensurvey_eda_validate.ipynb` | Phase 1.1+1.2 | opensurvey + 외부 reference (Coffee Sales, Bread Basket, PDF) | `output/prior_*.csv` (5종 분포 매트릭스), `output/validation_report.md` |
| `03_build_and_validate_synthetic.ipynb` | Phase 1.3+1.4+1.5 | prior_*.csv, rec_users, rec_items, rec_calendar, rec_weather | `output/kiosk_sessions.csv`, `kiosk_orders.csv`, `kiosk_order_items.csv` + `output/synthesis_validation.md` |
| `04_train_item2vec.ipynb` | Phase 2-A | transactions_clean.csv | `artifacts/item2vec_bread_basket.npy`, `menu_mapping.csv`, `artifacts/item2vec_kiosk_embeddings.npy` |
| `05_train_fm_context.ipynb` | Phase 2-B | kiosk_*.csv (자체 합성), rec_interactions.csv (비교) | `artifacts/fm_kiosk_weights.npz`, `fm_feature_encoder.pkl` |
| `06_evaluate_combine_export.ipynb` | Phase 3+4 | artifacts 전부 + holdout | `artifacts/eval_report.json`, backend `data/recommendation/` 일괄 export |

---

## 3. Phase 상세

### Phase 1.1 + 1.2 — OpenSurvey EDA + 외부 검증 (노트북 02)

#### 산출 prior 5종
1. `prior_demographics.csv` — P(user) = (gender × age_band × job × area).
2. `prior_menu_by_demographic.csv` — P(menu_category | gender, age_band).
3. `prior_brand_by_demographic.csv` — P(cafe_brand | demographic).
4. `prior_time_by_demographic.csv` — P(time_period | demographic).
5. `prior_menu_by_time.csv` — P(menu | time_period).

#### 외부 검증 항목
| 항목 | reference | 합격 기준 |
|---|---|---|
| 시간대별 방문 분포 | Coffee Sales (1년) + Bread Basket | 피크 시간 일치 |
| 카페 인기 순위 | NIQ Korea / Simon-Kucher | 상위 3위 일치 |
| 메뉴 카테고리 비중 | 학술 논문 (자료조사) | 카테고리 share 차이 <10%p |
| 인구 × 메뉴 상관 | 학술 논문 효과 크기 | 방향 일치 + 크기 ±30% |

검증 통과 → `prior_*` 그대로 사용. 어긋남 → 보정 메모.

### Phase 1.3+1.4+1.5 — 자체 합성 + 검증 (노트북 03)

#### 합성 spec (markdown 셀로 명세)
- 사용자: rec_users.csv 그대로 (2,000명).
- 메뉴: rec_items.csv 그대로 (30개) + 우리 카탈로그 22개 매핑.
- 영업 시간 / 시간대 분포: prior_time_by_demographic + Coffee Sales 분포.
- 인구 × 메뉴 prior: prior_menu_by_demographic.
- **컨텍스트 효과 크기 (가설 A~G)**:
  - A. 기온 ↑ → 아이스 +0.4/10°C.
  - B. 강수 → 핫 +10%p.
  - C. PM2.5 → 배달 +15%p.
  - D. 시간 → 카테고리 (prior_menu_by_time 매트릭스).
  - E. 시험 → 카페인 +15%.
  - F. 프로모 → 거래 빈도 +25%.
  - **G (★) 다중 라인 30~50%, 페어 분포 = Bread Basket 페어 매핑**.

#### 산출
- `kiosk_sessions.csv` — 세션 마스터.
- `kiosk_orders.csv` — 주문 (다중 라인 포함).
- `kiosk_order_items.csv` — 주문 항목.

#### 합성 검증 (같은 노트북 후반)
| 가설 | 합격 기준 |
|---|---|
| 인구 분포 | OpenSurvey와 KL < 0.05 |
| 시간대 분포 | reference와 피크 일치 |
| 인구 × 메뉴 상관 | OpenSurvey 매트릭스와 cosine > 0.85 |
| A~F 효과 크기 | spec ±20% |
| **G 다중 라인 비율** | **30~50%** |
| **G 페어 분포** | Bread Basket과 cosine > 0.6 |

전부 합격 → Phase 2 진입. 실패 → spec 조정 후 재합성 (최대 3회).

### Phase 2-A — Item2Vec (노트북 04)

- 입력: `transactions_clean.csv` (Bread Basket 정제).
- train/test split: 시간 기반 (마지막 N주 test).
- gensim Word2Vec(`vector_size=32, window=5, sg=1, epochs=20`).
- **메뉴 매핑**: Bread Basket 94 메뉴 → 우리 카탈로그 22 메뉴 (가중 평균).
- 우리 카탈로그 임베딩 산출 + 평가 (HitRate@K).

### Phase 2-B — FM (노트북 05)

- 입력 1: 자체 합성 (Phase 1 산출).
- 입력 2: rec_interactions.csv (비교용).
- negative sampling (랜덤 + 인기도 역가중, ratio 1:4).
- FM 학습 (PyTorch 단순 구현 또는 xLearn/pyFM).
- **컨텍스트 효과 재현 검증**: 학습 후 가중치가 가설 A~F와 일치하는지 (예: temp_x_is_ice 양수).
- 두 데이터셋 결과 비교, 자체 합성 우선 채택.

### Phase 3+4 — 평가·결합·export (노트북 06)

- 평가 메트릭: HitRate@5/10, NDCG@5/10, Coverage.
- 결합 가중치 α 그리드 서치 (0.0~1.0).
- baseline 비교: Popularity / Item-CF (cosine) / Item2Vec / FM / Item2Vec+FM.
- artifacts 정리 + `backend/data/recommendation/`로 export.
- backend 서비스 코드 신규 작성:
  - `services/item_embedding_service.py` — 임베딩 lookup + 카트 점수.
  - `services/context_fm_service.py` — FM 가중치 lookup + 컨텍스트 점수.
- `services/recommendation_service.py` 수정 — 두 신호 합류, **응답 스키마 불변**.

---

## 4. backend 통합 흐름 (Phase 4 완료 후 작동 검증)

```
recommend_v2(gender, age, cart_items, ...)
  ↓
1) 사용자 컨텍스트 조립 (age_band, hour, weather...)
  ↓
2) FM score (모든 후보 메뉴, 항상)
  ↓
3) Item2Vec score (cart 채워진 경우만)
  ↓
4) Combine
   if cart empty: final = fm_score
   else: final = α·fm + (1-α)·item2vec
   final *= trend_weight  (옵션)
  ↓
TOP-N 응답 (기존 응답 스키마 그대로)
```

---

## 5. 디렉토리 (확정)

```
create_data/
├── raw/
│   ├── bread basket.csv
│   └── kr_synthetic/
│       ├── opensurvey_cafe_2025_synthetic.csv
│       ├── rec_users.csv
│       ├── rec_items.csv
│       ├── rec_calendar.csv
│       ├── rec_weather_log.csv
│       └── rec_interactions.csv
├── notebooks/
│   ├── 01_eda_and_preprocess_colab.ipynb            (완료)
│   ├── 02_opensurvey_eda_validate.ipynb             ← 다음 작업
│   ├── 03_build_and_validate_synthetic.ipynb
│   ├── 04_train_item2vec.ipynb
│   ├── 05_train_fm_context.ipynb
│   └── 06_evaluate_combine_export.ipynb
├── synth/
│   └── effects.py                                    가설 효과 함수
├── output/                                           노트북 중간 산출
└── artifacts/                                        backend export 대상
```

---

## 6. 위험 + 대응

| 위험 | 대응 |
|---|---|
| Bread Basket 매핑 손실 (스무디·에이드 등 한국식 메뉴 부재) | 노트북 04 끝에서 메뉴 메타 기반 임베딩 보강 |
| FM이 자체 합성에 과적합 | 노트북 05에서 rec_interactions와 cross-validate, 앙상블 옵션 |
| 합성 검증 무한 루프 | 재합성 상한 3회 + 부분 합격 허용 |
| backend 응답 스키마 변경 우려 | 응답 불변 원칙. 점수 분해 필드만 응답에 추가 |
| Cold-start (카트 비음 + FM 미학습 메뉴) | 인기도 fallback 유지 |

---

## 7. 일정

| Phase | 노트북 | 예상 |
|---|---|---|
| Phase 1 | 02 + 03 | 1~2일 |
| Phase 2-A | 04 | 1일 |
| Phase 2-B | 05 | 1~2일 |
| Phase 3+4 | 06 + backend | 1~2일 |
| **합계** | | **5~7일** |

---

## 8. 진행 순서 (즉시 시작)

1. ✅ 검토 문서 갱신 (본 문서 + 02_CHANGE_REQUESTS.md + 05_DATASET_CANDIDATES.md).
2. ✅ 자산 복사 (자료조사 폴더 → `create_data/raw/kr_synthetic/`).
3. ➡️ **노트북 02 작성** (OpenSurvey EDA + 외부 검증, Colab 호환).
4. (사용자 실행 + 결과 보내주면) → 노트북 03 작성.
5. … (4~6 순차).
