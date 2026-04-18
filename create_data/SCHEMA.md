# 데이터 스키마 정리

## 1. 입력 원본 스키마

예상 원본:

- `transaction_id`
- `transaction_date`
- `transaction_time`
- `transaction_qty`
- `store_id`
- `store_location`
- `product_id`
- `unit_price`
- `product_category`
- `product_type`
- `product_detail`

## 2. 현재 프로젝트 목표 스키마

### kiosk_sessions.csv

| 컬럼 | 설명 |
|---|---|
| `session_id` | 내부 정수 식별자 |
| `started_at` | 세션 시작 시각 |
| `estimated_gender` | `M` 또는 `F` |
| `estimated_age_group` | `20~29`, `30~39`, `40~49`, `50+` |
| `is_simple_mode` | 고령/도움 모드 합성 |
| `help_triggered` | 안내 도움 발생 여부 |

### orders.csv

| 컬럼 | 설명 |
|---|---|
| `order_uuid` | 주문 UUID |
| `session_id` | 세션 FK |
| `created_at` | 주문 시각 |
| `total_price` | 주문 총액 |
| `status` | 기본 `completed` |
| `used_recommendation` | 추천 사용 여부 |

### order_items.csv

| 컬럼 | 설명 |
|---|---|
| `order_id` | 주문 FK |
| `menu_id` | 내부 메뉴 id |
| `quantity` | 수량 |
| `unit_price` | 단가 |
| `from_recommendation` | 추천 기여 여부 |

## 3. 중간 매핑 스키마

권장 파일:

- `interim/menu_mapping.csv`

권장 컬럼:

| 컬럼 | 설명 |
|---|---|
| `source_product_id` | 원본 상품 id |
| `source_product_detail` | 원본 상품명 |
| `source_category` | 원본 카테고리 |
| `normalized_menu_name` | 정규화 이름 |
| `normalized_category` | 정규화 카테고리 |
| `target_menu_id` | 현재 앱 메뉴 id |
| `keep` | 사용 여부 |

## 4. 추후 확장 스키마

필요 시 추가 가능:

- `recommendation_events.csv`
- `cart_snapshots.csv`

하지만 1차 구현은 `sessions`, `orders`, `order_items`에 집중하는 것이 적절하다.
