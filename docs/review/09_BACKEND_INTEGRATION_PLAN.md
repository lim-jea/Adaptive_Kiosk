# 09. v2 합성 데이터 → backend 적용 가이드

> 본 문서는 [08_TODAY_WORKLOG_2026-05-05.md](08_TODAY_WORKLOG_2026-05-05.md) 의 후속이며, 격리 환경에서 검증한 v2 합성 데이터를 실제 backend 에 어떻게 반영할지 정리한다. 또한 향후 v3, v4 등 새 후보를 만들 때의 표준 절차로도 사용한다.

## 0. 채택안 요약

- **추천 알고리즘**: backend 기존 `services/recommendation_service.py` 의 통계 기반 엔진 그대로. 코드 변경 없음.
- **추천 데이터**: `create_data/recommendation_test/data2/` 의 3개 CSV (v2 합성 결과).
- **거부**: Item2Vec / FM / LightFM / ALS 등 모든 학습형 모델 — WEAK 판정으로 미채택. 자세한 내용은 [02_CHANGE_REQUESTS.md](02_CHANGE_REQUESTS.md) 의 CHANGE-014/015 REJECTED 참고.

## 1. 사전 조건 — 격리 검증 완료 확인

backend/data 에 반영하기 전, 다음 조건이 모두 만족되어야 한다.

```powershell
cd create_data/recommendation_test
python run_test.py --compare
```

`comparison_report.md` 에서 v2(synth2) 행이 다음 기준을 모두 통과하는지 확인:

| 항목 | 기준 | v2 현재값 |
|---|---|---|
| sessions | ≥ 10,000 | 50,000 ✅ |
| items/order | ≥ 1.5 | 1.66 ✅ |
| HHI (메뉴 집중도) | ≤ 0.06 | 0.0457 ✅ |
| 단일 메뉴 max share | ≤ 6% | 5.15% ✅ |
| context-level unique top1 (40 컨텍스트) | ≥ 15 | 18 ✅ |
| co_purchase 메뉴 수 | = 22 | 22 ✅ |
| 컨텍스트별 추천이 시간대/인구별로 분리되는가 (육안) | 분리됨 | 통과 ✅ |

**중요**: v2 generator 의 `hour_to_period` 와 `PERIOD_ADJ` 키는 backend `recommendation_service._hour_to_period` 와 **동일한 5개 period** (`morning, lunch, afternoon, evening, night`) 를 사용하도록 동기화되어 있다. 추후 backend 의 period 경계가 변경되면 generator 도 동시에 갱신해야 함.

## 2. 적용 절차 (Windows / PowerShell)

```powershell
cd create_data/recommendation_test

# 1) backend 기존 데이터 백업 (롤백 가능하도록)
$bk = "../../backend/data/_legacy"
New-Item -Force -ItemType Directory -Path $bk | Out-Null
Copy-Item ../../backend/data/kiosk_sessions.csv $bk/
Copy-Item ../../backend/data/orders.csv         $bk/
Copy-Item ../../backend/data/order_items.csv    $bk/

# 2) v2 데이터로 교체
Copy-Item -Force data2/kiosk_sessions.csv ../../backend/data/
Copy-Item -Force data2/orders.csv         ../../backend/data/
Copy-Item -Force data2/order_items.csv    ../../backend/data/
```

## 3. backend 재기동 후 동작 검증

```powershell
# backend 시작
cd ../../backend
uv run uvicorn main:app --reload
```

부팅 로그에서 다음을 확인:

```
Recommendation CSV loaded: 50000 sessions, 50000 orders, 83042 items
Recommendation menu mapping updated: 22 menus
```

(menu mapping 22 가 아니면 seed_menu 와 메뉴 ID 불일치 — drop된 메뉴가 섞였거나 mapping json 이 옛 버전)

API 검증:
```powershell
# 모드 A 추천 호출 예시 (실제 endpoint 는 backend router 코드 확인)
curl http://localhost:8000/recommendations/mode-a?gender=여&age_group=20대&hour=9
```

기대 결과: 4개 컨텍스트(여20대 9h, 여30대 13h, 남30대 19h, 남50대 8h) 응답이 v2 격리 검증 결과와 **일치**해야 한다 (cache 채워지기 전 첫 호출은 cold 일 수 있으니 두 번째부터 비교).

## 4. 롤백 절차

문제가 발견되면:

```powershell
cd backend
Copy-Item -Force data/_legacy/kiosk_sessions.csv data/
Copy-Item -Force data/_legacy/orders.csv         data/
Copy-Item -Force data/_legacy/order_items.csv    data/
# 재기동
```

## 5. 향후 v3, v4 후보 생성 표준 절차

신 후보 데이터를 만들 때는 `recommendation_test/` 격리 환경에서만 작업한다 (backend 코드/데이터 직접 영향 X).

```powershell
cd create_data/recommendation_test

# (1) 새 prior 로 생성기 실행 — 기존 generator 를 복사해 _v3.py 로 만들어 prior 만 수정
python generate_synth_v3.py --n-sessions 50000 --seed 42 \
    --out source_synthetic3 --max-share 0.06

# (2) backend 스키마로 변환
python sync_synthetic_data.py --source source_synthetic3 --target data3

# (3) run_test.py 의 DATASET_DIRS 에 "synth3": SYNTH3_DIR 추가 후
python run_test.py --compare-sets legacy synth2 synth3

# (4) 가장 좋은 후보가 v3 면 절차 2 의 절차로 backend 반영, 백업 파일은 _legacy/, _legacy_v2/ 식으로 누적
```

**v3 가 만족시켜야 하는 추가 기준** (v2 대비 개선):
- v2 의 컨텍스트별 추천이 시간/인구 의도와 일치하는지 육안 점검에서 어색했던 케이스가 있었다면, v3 의 prior 보정으로 그 케이스가 해소되어야 한다.
- 통계 지표 (HHI, max share, unique top1) 는 v2 수준 이상.
- co_purchase 의 페어 다양성: 두 메뉴 간 비현실적 페어(예: 에스프레소 + 망고스무디 1위)가 줄었는가.

## 6. backend 코드 자체를 수정해야 하는 경우

격리 검증 중 **데이터가 아니라 엔진 자체** 의 결함이 발견되면 backend 코드를 직접 수정한다. 주의:

- `recommendation_service_copy.py` 는 격리 검증 전용 복사본. **직접 편집 금지** — backend 원본만 수정 후 본 복사본은 새로 동기화.
- 수정 영역 후보:
  - period 경계 (현재 4시간 단위) — 카페 영업 사이클에 더 맞게 5단위로 재설계 시
  - co-purchase 점수 → 추천 결합 가중치 — 현재 mode A 기본 추천에서 co-purchase 영향이 작음
  - popularity bias 보정 — 컨텍스트별 메뉴 빈도와 전체 빈도 차이를 lift 로 재정렬
- 변경 시 [02_CHANGE_REQUESTS.md](02_CHANGE_REQUESTS.md) 에 새 CHANGE 항목으로 기록.

## 7. 캡스톤 보고서에서의 서술 가이드

- “모델형 추천 시도(Item2Vec/FM/LightFM/ALS)는 합성 데이터 baseline 대비 의미 있는 lift 를 보이지 않아(8번 노트북 ablation에서 WEAK 판정) **데이터 품질 개선** 으로 노선 변경.”
- “backend 기존 통계 기반 엔진을 유지하되, 입력 데이터를 (a) Maven Coffee Shop 가공 → (b) v1 OpenSurvey prior 합성 → (c) v2 prior 명시적 분리 + softmax cap 합성, 으로 단계적 개선.”
- “v2 의 핵심 개선 — 단일 메뉴 도배(말차 9.84%) 차단 + 시간대/인구 차원의 메뉴 분리력 확보(컨텍스트 unique top1 3 → 18).”

## 8. 산출 파일 목록 (오늘 시점)

| 분류 | 경로 | 비고 |
|---|---|---|
| 격리 검증 환경 | `create_data/recommendation_test/` | 본 폴더 README 참조 |
| v2 생성기 | `create_data/recommendation_test/generate_synth_v2.py` | prior + iterative cap |
| v2 source CSV | `create_data/recommendation_test/source_synthetic2/` | generate_synth_v2.py 산출 |
| v2 backend 스키마 CSV | `create_data/recommendation_test/data2/` | backend 반영 대상 |
| 비교 리포트 | `create_data/recommendation_test/comparison_report.{md,json}` | 최신 3-way 결과 |
| 작업 로그 | `docs/review/08_TODAY_WORKLOG_2026-05-05.md` | 오늘 timeline |
| 본 가이드 | `docs/review/09_BACKEND_INTEGRATION_PLAN.md` | (이 파일) |
| 거부된 시도 보존 | `../../research_archive/` (repo 외부) | INDEX.md 로 정리. git 미추적 |
