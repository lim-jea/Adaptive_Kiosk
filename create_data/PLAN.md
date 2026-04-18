# 합성 데이터 구축 계획

## 1. 목표

외부 주문 데이터셋을 현재 Adaptive Kiosk 추천 구조에 맞는 합성 데이터로 변환한다.

핵심 목표:

- 추천 시스템 학습/통계용 주문량 확보
- 현재 백엔드 CSV 입력 포맷 유지
- 카페 키오스크 도메인에 맞는 옵션/프로필 정보 합성

## 2. 사용할 원본 데이터

우선 후보:

- Kaggle `Coffee Shop Sales`

기대 원본 컬럼 예시:

- `transaction_id`
- `transaction_date`
- `transaction_time`
- `transaction_qty`
- `store_id`
- `product_id`
- `unit_price`
- `product_category`
- `product_type`
- `product_detail`

## 3. 현재 프로젝트에 필요한 최종 데이터셋

### 3.1 kiosk_sessions.csv

필수 컬럼:

- `session_id`
- `session_uuid` 또는 내부 식별자
- `started_at`
- `estimated_gender`
- `estimated_age_group`
- `is_simple_mode`
- `help_triggered`

합성 규칙:

- 주문 1건당 세션 1개를 기본으로 생성
- 성별은 `M/F` 비율 기반 랜덤 생성
- 연령대는 `20~29`, `30~39`, `40~49`, `50+`로 생성
- `is_simple_mode`는 고연령대에서 더 높은 확률 부여

### 3.2 orders.csv

필수 컬럼:

- `order_uuid`
- `session_id`
- `created_at`
- `total_price`
- `status`
- `used_recommendation`

변환 규칙:

- 원본 `transaction_id`를 주문 식별자로 사용
- 날짜 + 시간 결합 후 `created_at` 생성
- `transaction_qty * unit_price` 합산으로 `total_price` 계산
- `status`는 기본 `completed`
- `used_recommendation`은 확률 기반 합성

### 3.3 order_items.csv

필수 컬럼:

- `order_id`
- `menu_id`
- `quantity`
- `unit_price`
- `from_recommendation`

변환 규칙:

- 한 주문 안의 각 품목 행을 그대로 아이템으로 사용
- `product_id`를 내부 `menu_id`로 매핑
- `transaction_qty`를 `quantity`로 사용
- `from_recommendation`은 주문 레벨 플래그와 연동해 일부만 true 부여

## 4. 메뉴 매핑 계획

원본 메뉴명과 현재 앱의 메뉴는 바로 일치하지 않을 수 있다.

그래서 중간 매핑 테이블이 필요하다.

필수 매핑 필드:

- `source_product_id`
- `source_product_detail`
- `normalized_menu_name`
- `normalized_category`
- `target_menu_id`

규칙:

- 현재 `backend`의 `menus`와 최대한 이름을 맞춘다.
- 너무 세분화된 원본 메뉴는 현재 키오스크 메뉴로 묶는다.
- 현재 앱에 없는 메뉴는 제외하거나 가장 가까운 메뉴로 합친다.

## 5. 옵션 합성 계획

원본 데이터에는 옵션이 거의 없으므로 현재 `menu_options`를 기준으로 합성한다.

### 5.1 그룹별 기본 규칙

- 커피:
  - `size`
  - `temperature`
  - `shot`
- 티:
  - `size`
  - `temperature`
  - `sweetness`
- 에이드/스무디:
  - `size`
  - `ice`
  - `sweetness`

### 5.2 합성 방식

- 메뉴 카테고리별로 허용 옵션 그룹 지정
- 각 그룹에서 확률 기반으로 선택
- 필수 옵션은 항상 채움
- 주문 이력 CSV에는 당장 옵션 컬럼이 없더라도, 나중에 필요하면 별도 산출물로 유지

## 6. 추천 관련 플래그 합성 계획

현재 구조에는 아래 값들이 존재한다.

- `orders.used_recommendation`
- `order_items.from_recommendation`

합성 규칙 초안:

- 기본 추천 사용률 예: 10~20%
- 장바구니에 여러 품목이 있을수록 추천 아이템 비율을 조금 높임
- `used_recommendation = true`인 주문에서는 적어도 한 개 `order_item.from_recommendation = true`

## 7. 데이터 품질 검증

생성 후 반드시 확인할 것:

- `orders.total_price == order_items 합계`
- `order_items.menu_id`가 유효한 메뉴를 참조하는지
- 연령대/성별 값이 추천 시스템 허용 범위인지
- 시간대 분포가 과도하게 한쪽으로 쏠리지 않았는지
- `used_recommendation`과 `from_recommendation` 논리가 일관적인지

## 8. 구현 우선순위

1. 원본 CSV 로더
2. 메뉴 정규화/매핑
3. `orders.csv`, `order_items.csv` 생성
4. `kiosk_sessions.csv` 합성
5. 추천 플래그 합성
6. 검증 스크립트
7. 필요 시 옵션/추천 이벤트 추가 생성

## 9. 최종 판단

현재 프로젝트에서 가장 먼저 필요한 것은:

- 옵션까지 완벽한 데이터셋이 아니라
- 충분히 큰 주문 transaction 데이터
- 현재 추천 구조가 그대로 읽을 수 있는 CSV 포맷

즉 1차 목표는:

- `Coffee Shop Sales`를 기반으로
- `sessions + orders + order_items`를 안정적으로 만드는 것

이다.
