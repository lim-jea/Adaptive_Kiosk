# Create Data

합성 주문 데이터 구축용 작업 폴더다.

목표는 추천 엔진(`backend/services/recommendation_service.py`)이 바로 읽을 수 있는 CSV를 생성하는 것이다.

> **현재 채택안 (2026-05-05)**: `recommendation_test/generate_synth_v2.py` 의 prior 기반 합성. 격리 검증 완료.
> 자세한 내용 → [docs/review/08_TODAY_WORKLOG_2026-05-05.md](../docs/review/08_TODAY_WORKLOG_2026-05-05.md), [docs/review/09_BACKEND_INTEGRATION_PLAN.md](../docs/review/09_BACKEND_INTEGRATION_PLAN.md).

## 폴더 구조

```text
create_data/
├── README.md / PLAN.md / SCHEMA.md
├── notebooks/              # 활성 EDA·합성 검증 노트북
│   ├── 01_eda_and_preprocess[_colab].ipynb
│   ├── 02_opensurvey_eda_validate.ipynb
│   └── 03_build_and_validate_synthetic.ipynb
├── raw/                    # 원본 prior 데이터
│   └── kr_synthetic/       # OpenSurvey 카페 응답 + rec_* 합성 origin
├── interim/                # 노트북 중간 산출
├── output/                 # 03 노트북 실행 결과 (참고용 노트북 사본)
└── recommendation_test/    # ★ 격리 검증 + v2 생성기 (현재 핵심 작업 폴더)
```

> 거부된 모델 시도 / 외부 데이터 / 대체된 합성 산출은 **repo 외부**의 `../research_archive/` 로 이동되어 보존된다 (git 미추적). 자세한 내역은 그 폴더의 `INDEX.md` 참조.

## 활성 작업 흐름 (v2 채택안 기준)

```powershell
cd create_data/recommendation_test

# (1) 합성 데이터 생성 (prior + softmax cap 6%)
python generate_synth_v2.py --n-sessions 50000 --seed 42

# (2) backend 스키마로 변환
python sync_synthetic_data.py --source source_synthetic2 --target data2

# (3) 격리 검증 (legacy + v1 + v2 비교 리포트)
python run_test.py --compare

# (4) 통과 시 backend 반영 — 절차는 09_BACKEND_INTEGRATION_PLAN.md
```

## 추천 엔진과 연결되는 데이터 보장 사항

`RecommendationEngine` 이 사용하는 컬럼:

- 주문 시간 (`orders.created_at`)
- 주문별 아이템 묶음 (`order_items.order_id`)
- 메뉴 id (`order_items.menu_id`) — backend `seed_menu` 22 메뉴 1-based ID
- 세션별 성별·연령대 (`kiosk_sessions.estimated_gender`, `estimated_age_group`) — 한국어 라벨 (`남`/`여`, `20대`~`50대`)

## 거부/대체된 자료 (repo 밖 보존)

본 폴더에서 빠진 옛 시도들은 모두 **repo 외부**의 `../research_archive/` 에 보존되어 있다 (git 미추적). 폴더 구조:

- `rejected_notebooks/` — Item2Vec / FM / LightFM / ALS 학습 노트북 (효과 없음)
- `rejected_artifacts/` — 학습 산출물
- `early_cf_attempts/` — user/item-based CF 초기 시도 (외부 데이터 mismatch)
- `external_datasets/` — Bread Basket / Restaurant_Orders / Maven Coffee Shop / Starbucks 등 외부 라이선스 데이터
- `superseded_synthetic/` — backend 미반영 v0 합성 데이터
- `deprecated_scripts/` — `build_dataset.py` 등 사용 종료 스크립트
- `INDEX.md` — 각 폴더의 보존 사유와 거부 사유 요약

캡스톤 보고서 작성 시에는 `../research_archive/INDEX.md` 의 §7 인용 가이드를 참고.

## 캡스톤 보고서에서의 인용 가이드

데이터 생성 의사결정 트리:
1. **외부 공개 데이터 직접 사용** → mismatch 로 거부 (research_archive/external_datasets/)
2. **Maven Coffee Shop 가공** → backend 의 현재 데이터로 반영. 한국 카페 메뉴와 mismatch.
3. **OpenSurvey prior 합성 v1** → 통계량은 풍부하나 단일 메뉴(말차) 도배 + 컨텍스트 분리력 부족
4. **prior 기반 합성 v2** ← **현재 채택안**. 명시적 prior + softmax cap + backend period 정렬
