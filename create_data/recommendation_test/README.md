# Recommendation Engine — 격리 테스트 + 합성 데이터 반복 개선 환경

> backend `services/recommendation_service.py` 를 손대지 않고, **합성 데이터를 입력으로 줬을 때 추천이 어떻게 나오는지** 격리 환경에서 검증한 뒤, 가장 좋은 데이터를 backend/data 에 반영한다.

## 폴더 구성

```
recommendation_test/
├── README.md                       ← 본 문서
├── recommendation_service_copy.py  ← backend 의 추천 엔진 복사본 (편집 금지)
├── menu_id_mapping.json            ← rec_items 30개 → backend seed_menu 22개 매핑
├── sync_synthetic_data.py          ← 합성 CSV → backend 스키마 변환
├── generate_synth_v2.py            ← v2 합성 데이터 생성기 (prior 기반)
├── run_test.py                     ← 추천 엔진을 격리 실행 + N-way 비교 리포트
│
├── source_synthetic2/              ← v2 합성 데이터 (generate_synth_v2.py 산출)
├── data2/                          ← v2 → backend 스키마 변환 결과 (= backend/data 와 동일)
│
├── comparison_report.md            ← 최신 비교 리포트 (사람용, 검증 증거)
└── comparison_report.json          ← 최신 비교 리포트 (정량)
```

> **legacy 비교**는 `LEGACY_DIR = backend/data/_legacy` 를 자동 참조하므로 `legacy_data/` 별도 복사본을 두지 않는다.
> **v1 산출물(`source_synthetic/`, `data/`)** 은 v2 채택 후 정리됨. 비교 결과는 `comparison_report.{md,json}` 에 박제되어 있다.

## 0단계: legacy 데이터 (자동)

`run_test.py` 의 `LEGACY_DIR` 가 `backend/data/_legacy/` 를 가리킨다.
backend 에 v2 를 반영했을 때 `09_BACKEND_INTEGRATION_PLAN.md` §2 에서 자동 백업되며, 이 백업이 legacy 비교 baseline 으로 사용된다.

## 1단계: v2 합성 데이터 생성

```powershell
python generate_synth_v2.py --n-sessions 50000 --seed 42 --max-share 0.06
python sync_synthetic_data.py --source source_synthetic2 --target data2
```

`generate_synth_v2.py` 의 핵심 prior:
- `PERIOD_ADJ` — 시간대 (morning/lunch/afternoon/evening/night, backend 와 동일) × 메뉴 가중치
- `GENDER_AGE_ADJ` — (성별, 연령) × 메뉴 가중치
- `softmax_capped(max_share=0.06)` — 어떤 메뉴도 전체의 6% 를 넘지 못하게 iterative cap

## 2단계: 비교 실행

```powershell
python run_test.py --compare                          # 등록된 모든 데이터셋
python run_test.py --compare-sets legacy synth2       # 부분 비교
python run_test.py --dataset synth2                   # 단일 데이터셋 디버깅
```

새 후보 (v3, v4) 추가 시: `DATASET_DIRS` 에 항목 추가 후 동일 명령으로 비교.

산출:
- `comparison_report.md` — 사람용 비교 리포트 (데이터셋 요약 표 + 컨텍스트별 추천)
- `comparison_report.json` — 정량 결과

## 3단계: 점검 포인트 (v2 검증 결과 — 2026-05-05)

| 항목 | legacy | v1 | **v2** | 목표 |
|---|---|---|---|---|
| sessions | 2,000 | 45,709 | 50,000 | ≥ 10k |
| items/order | 1.50 | 1.32 | **1.66** | ≥ 1.5 |
| HHI | 0.0579 | 0.0565 | **0.0457** | ≤ 0.06 |
| 단일 메뉴 max share | 9.05% | 9.84% | **5.17%** | ≤ 6% |
| context unique top1 | 7/40 | 3/40 | **18/40** | ≥ 15 |

→ **v2 모든 점검 항목 통과**.

## 4단계: backend 반영 — **2026-05-05 완료** ✅

backend/data/ 에 v2 적용 완료. 이전 데이터는 `backend/data/_legacy/` 에 백업.
적용 절차/롤백 절차/v3 신규 후보 추가 절차는 [`docs/review/09_BACKEND_INTEGRATION_PLAN.md`](../../docs/review/09_BACKEND_INTEGRATION_PLAN.md) 참고.

## 주의

- `recommendation_service_copy.py` 는 backend 원본의 단순 복사본. **편집 금지.** 검증 중 backend 코드 자체 수정 필요가 발견되면 별도 PR 로 backend 에 직접 반영.
- 본 폴더 산출물(`data/`, `data2/`, `source_synthetic*/`)은 .gitignore 후보. backend 에 반영하기 전까지 backend 동작에 영향 없음.
