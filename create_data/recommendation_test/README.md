# Recommendation Engine — 격리 테스트 + 합성 데이터 반복 개선 환경

> backend `services/recommendation_service.py` 를 손대지 않고, **합성 데이터를 입력으로 줬을 때 추천이 어떻게 나오는지** 격리 환경에서 검증한 뒤, 가장 좋은 데이터를 backend/data 에 반영한다.

## 폴더 구성

```
recommendation_test/
├── README.md                       ← 본 문서
├── recommendation_service_copy.py  ← backend 의 추천 엔진 복사본 (편집 금지)
├── menu_id_mapping.json            ← rec_items 30개 → backend seed_menu 22개 매핑
├── sync_synthetic_data.py          ← 합성 CSV → backend 스키마 변환
├── generate_synth_v2.py            ← v2 합성 데이터 생성기 (prior 기반, 본 폴더 단독)
├── run_test.py                     ← 추천 엔진을 격리 실행 + N-way 비교 리포트
│
├── source_synthetic/               ← v1 합성 데이터 (Drive output 산출 + sex/age 라벨)
├── source_synthetic2/              ← v2 합성 데이터 (generate_synth_v2.py 산출)
│   └── kiosk_{sessions,orders,order_items}.csv
│
├── data/                           ← v1 → backend 스키마 변환 결과
├── data2/                          ← v2 → backend 스키마 변환 결과
├── legacy_data/                    ← backend/data 에서 복사한 기존 (Maven) 데이터
│
├── comparison_report.md            ← 최신 비교 리포트 (사람용)
└── comparison_report.json          ← 최신 비교 리포트 (정량)
```

## 0단계: legacy 데이터 확보 (1회)

backend/data 의 현재 CSV 3개를 `legacy_data/` 에 복사. 이미 되어 있으면 skip.

## 1단계: v1 합성 데이터 (Drive 출력본)

Drive `output/` 의 다음 3개 파일을 `source_synthetic/` 에 복사:
- `kiosk_sessions.csv`, `kiosk_orders.csv`, `kiosk_order_items.csv`

```powershell
python sync_synthetic_data.py            # source_synthetic → data
```

## 2단계: v2 합성 데이터 (본 폴더 단독 생성)

v1 의 단일-메뉴 도배 문제를 해결한 prior 기반 생성기.

```powershell
python generate_synth_v2.py --n-sessions 50000 --seed 42 --max-share 0.06
python sync_synthetic_data.py --source source_synthetic2 --target data2
```

generate_synth_v2.py 의 핵심 prior:
- `PERIOD_ADJ` — 시간대(morning/lunch/afternoon/dinner/late) × 메뉴 가중치
- `GENDER_AGE_ADJ` — (성별, 연령) × 메뉴 가중치
- `softmax_capped(max_share=0.06)` — 어떤 메뉴도 전체의 6% 를 넘지 못하게 iterative cap

## 3단계: 비교 실행

```powershell
python run_test.py --compare                          # 3-way (legacy + synth + synth2)
python run_test.py --compare-sets legacy synth2       # 2-way (예: 최종 후보만)
python run_test.py --dataset synth2                   # 단일 데이터셋 디버깅
```

산출:
- `comparison_report.md` — 사람용 비교 리포트 (데이터셋 요약 표 + 컨텍스트별 추천)
- `comparison_report.json` — 정량 결과

## 4단계: 점검 포인트 (v2 검증 결과 — 2026-05-05)

| 항목 | legacy | v1 | **v2** | 목표 |
|---|---|---|---|---|
| sessions | 2,000 | 45,709 | 50,000 | ≥ 10k |
| items/order | 1.50 | 1.32 | **1.66** | ≥ 1.5 |
| HHI | 0.0579 | 0.0565 | **0.0457** | ≤ 0.06 |
| 단일 메뉴 max share | 9.05% | 9.84% | **5.17%** | ≤ 6% |
| context unique top1 | 7/40 | 3/40 | **18/40** | ≥ 15 |

→ **v2 모든 점검 항목 통과**.

## 5단계: backend 반영 — `docs/review/09_BACKEND_INTEGRATION_PLAN.md` 참고

요약:
```powershell
mkdir -Force ../../backend/data/_legacy
Copy-Item ../../backend/data/kiosk_sessions.csv ../../backend/data/_legacy/
Copy-Item ../../backend/data/orders.csv         ../../backend/data/_legacy/
Copy-Item ../../backend/data/order_items.csv    ../../backend/data/_legacy/

Copy-Item data2/kiosk_sessions.csv ../../backend/data/
Copy-Item data2/orders.csv         ../../backend/data/
Copy-Item data2/order_items.csv    ../../backend/data/
```

backend 재기동 시 `recommendation_engine.load_data()` 가 자동으로 새 데이터를 로드.

## 주의

- `recommendation_service_copy.py` 는 backend 원본의 단순 복사본. **편집 금지.** 검증 중 backend 코드 자체 수정 필요가 발견되면 별도 PR 로 backend 에 직접 반영.
- 본 폴더 산출물(`data/`, `data2/`, `source_synthetic*/`)은 .gitignore 후보. backend 에 반영하기 전까지 backend 동작에 영향 없음.
