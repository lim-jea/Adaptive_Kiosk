# Create Data

합성 주문 데이터 구축용 작업 폴더다.

목표는 외부 카페 주문 데이터셋을 현재 프로젝트 구조에 맞게 가공해서,
추천 시스템과 분석 기능이 바로 읽을 수 있는 CSV를 생성하는 것이다.

## 왜 별도 폴더로 분리하나

- `backend/` 런타임 코드와 데이터 생성 코드를 분리하기 위해
- 데이터 전처리, 합성, 검증 로직을 독립적으로 관리하기 위해
- 나중에 다른 데이터셋이나 생성 규칙을 실험하기 쉽게 만들기 위해

## 현재 기준 산출물

최종 산출물은 아래 3개를 우선 목표로 한다.

- `backend/data/kiosk_sessions.csv`
- `backend/data/orders.csv`
- `backend/data/order_items.csv`

선택 산출물:

- `backend/data/recommendation_events.csv`
- `backend/data/cart_snapshots.csv`

## 현재 추천 시스템과 연결되는 핵심 포인트

- `RecommendationEngine`은 현재 `orders.csv`, `order_items.csv`, `kiosk_sessions.csv`를 읽는다.
- `mode_a`는 `성별 × 연령대 × 시간대` 통계를 쓴다.
- `mode_b`는 `같은 주문 안의 공구매 관계`를 쓴다.

즉 합성 데이터도 최소한 아래는 보장해야 한다.

- 주문 시간
- 주문별 아이템 묶음
- 메뉴 id
- 수량
- 세션별 성별/연령대

## 권장 작업 순서

1. 원본 데이터셋을 `raw/`에 저장
2. 메뉴 매핑 규칙 작성
3. 주문 헤더/주문 아이템 추출
4. 세션 프로필 합성
5. 옵션 및 추천 관련 플래그 합성
6. CSV 검증
7. `backend/data/`로 내보내기

## 폴더 제안

```text
create_data/
├── README.md
├── PLAN.md
├── SCHEMA.md
├── raw/                 # 원본 데이터셋
├── interim/             # 중간 가공 결과
├── output/              # 최종 생성 CSV
├── build_dataset.py     # 매핑/생성/검증 통합 스크립트
└── scripts/             # 과거 스크립트 폴더 (정리 대상)
```

## 현재 추천 데이터셋 방향

메인 베이스 데이터셋:

- Kaggle `Coffee Shop Sales`

이 데이터셋은 주문 로그와 메뉴 축을 제공하므로,
현재 프로젝트에서는 `옵션`, `성별`, `연령대`, `추천 사용 여부`를 합성해서 붙이는 방식이 적절하다.

## 바로 사용할 스크립트

- `build_dataset.py`
  - 원본 상품 매핑 생성
  - 세션/주문/주문아이템 CSV 생성
  - 출력 검증
  - 필요 시 `backend/data/`로 바로 반영

## 원본 파일 위치

아래 위치에 원본 파일을 넣으면 됩니다.

- [create_data/raw](C:\Users\jeayy\Desktop\26년도 산학협력캡스톤\Adaptive_Kiosk\create_data\raw)

지원 형식:

- `.csv`
- `.xlsx`
- `.xls`

필수 컬럼은 아래와 같습니다.

- `transaction_id`
- `transaction_date`
- `transaction_time`
- `transaction_qty`
- `product_id`
- `unit_price`
- `product_category`
- `product_type`
- `product_detail`

엑셀 파일(`.xlsx`)을 그대로 쓰려면 현재 Python 환경에 `openpyxl`이 필요합니다.
설치가 번거로우면 엑셀에서 CSV로 한 번 저장해서 넣는 방식이 가장 간단합니다.

## 기본 사용 순서

```bash
cd create_data
python build_dataset.py
```

`backend/data/`에 바로 덮어쓰고 싶으면:

```bash
python build_dataset.py --publish-to-backend
```

메뉴 매핑만 다시 만들고 싶으면:

```bash
python build_dataset.py --mapping-only
```

생성 결과만 다시 검증하고 싶으면:

```bash
python build_dataset.py --validate-only
```
