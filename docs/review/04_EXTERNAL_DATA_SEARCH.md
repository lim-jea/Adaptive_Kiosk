# 외부 데이터 탐색 가이드 (Item2Vec CF용)

> 본 문서는 사용자가 외부 카페/소매 트랜잭션 데이터셋을 직접 검색해서 가져오기 위한 요건 정리.
> 후속 작업 계획: [02_CHANGE_REQUESTS.md](./02_CHANGE_REQUESTS.md) CHANGE-004 / 008 / 009 / 010 / 011 와 연계.

---

## 1. 결정된 방향

- CF 종류: **Item2Vec (Prod2Vec)** — 한 주문 = 한 문장으로 학습. 사용자 차원 불필요.
- 통합: **C-3** — 카트가 비었을 때는 기존 인기도, 카트 채워지면 CF 합류.
- 학습 데이터 출처: **외부 실데이터 우선 탐색**. 없으면 합성 보강(B-1)으로 fallback.

---

## 2. 필요한 데이터 요건

### 필수 (없으면 사용 불가)
1. 한 주문(영수증) 안에 **여러 메뉴**가 들어 있는 데이터.
   - 검증: `groupby(order_id).item_id.nunique() >= 2` 인 주문 비율 **30% 이상**.
2. 메뉴(아이템)에 **식별 가능한 ID 또는 일관된 이름**.
3. **카페·F&B·베이커리·소매** 도메인 (매핑 가능한 범위).
4. **공개 라이선스** (Kaggle, UCI, AIHub, 공공데이터, CC-BY 등).
5. **데이터량**: 주문 5,000건 + 메뉴 ID 30개 이상.

### 권장 (있으면 추천 품질↑)
- 주문 시각 (timestamp).
- 고객/세션 식별자 (있으면 모델 기반 CF 확장 가능).
- 메뉴 메타데이터 (카테고리, 가격, 핫/아이스).
- 인구통계 (성별, 연령대, 지역) — CHANGE-010을 실데이터로 자연 해결.
- 주문 채널 (매장/배달/온라인).

### 보너스 (없어도 무관)
옵션 정보, 결제 수단, 리뷰/평점, 영업일/공휴일.

---

## 3. 우선순위별 후보 데이터셋 / 검색 키워드

### 1순위 — 카페/F&B 직접
| 검색 키워드 | 출처 | 비고 |
|---|---|---|
| `cafe pos transaction dataset` | Kaggle, GitHub | 직접 카페 |
| `coffee shop pos receipts` | Kaggle, data.world | 영수증 단위 |
| `restaurant orders dataset multi item` | Kaggle, GitHub | 식음료 |
| `bakery transactions association rules` | Kaggle ("Bakery Sales") | 베이커리 + 카페 결합 |
| `cafeteria food sales basket` | UCI, OpenML | 학교 카페테리아 |
| `Brazilian restaurant orders dataset` | Kaggle | 다국적 |

**유망 후보**:
- Kaggle "Bakery Sales / Bread Basket Analysis" — 영수증 다중 라인 풍부.
- Kaggle "Restaurant 1k orders" / "Restaurant Orders Dataset".

### 2순위 — 소매 트랜잭션 (음료 카테고리만 필터)
| 데이터셋 | 특징 | 매핑 난이도 |
|---|---|---|
| Instacart "Market Basket Analysis" | 다중 라인, 사용자 ID | 중 (음료만 추출) |
| Online Retail II (UCI) | 다중 SKU | 높음 |
| Dunnhumby / Tafeng | 사용자·인구통계 | 중상 |
| Olist Brazilian E-commerce | 영수증·고객 연결 | 높음 |

### 3순위 — 한국 데이터
- AI Hub `K-푸드` 메뉴/주문.
- 공공데이터포털 `카페 매출 데이터`.
- 서울시 우리마을가게 상권 분석.
- 장점: 한국어 메뉴명 자동 매핑.

---

## 4. 다운로드 후 즉시 검증 코드

```python
import pandas as pd
df = pd.read_csv("downloaded.csv")

# (1) 컬럼 확인
print(df.columns.tolist())

# (2) 다중 라인 비율
multi = df.groupby("order_id")["item_id"].nunique()
print("distinct items per order:", multi.describe())
print("orders with >=2 distinct items:",
      int((multi >= 2).sum()),
      f"({(multi>=2).mean()*100:.1f}%)")

# (3) 메뉴 다양성
print("distinct items total:", df["item_id"].nunique())

# (4) 시간 정보
print("has timestamp:",
      any(c for c in df.columns if "time" in c.lower() or "date" in c.lower()))

# (5) 인구통계
print("has user info:",
      any(c.lower() in {"customer_id","user_id","gender","age","age_group"}
          for c in df.columns))
```

### 합격 기준
- (2)의 비율이 **30% 이상**.
- (3) 메뉴 30개 이상.
- 라이선스 명확.

---

## 5. 데이터 발견 후 통합 순서

1. 메뉴 매핑 테이블 작성 (외부 메뉴명 → 우리 카탈로그 22개).
2. `create_data/build_dataset_external.py` 추가 (기존 `build_dataset.py`는 백업/대조용).
3. (필요 시) 인구통계 prior 합성 — CHANGE-010 방식.
4. `backend/services/item_embedding_service.py` 추가 — Item2Vec 학습.
5. `recommendation_service.py`에 CF 시그널 합류 (C-3 흐름).
6. 추천 점수 분해(`cf_breakdown`)에 `item2vec_score` 필드 추가.

---

## 6. 사용자가 데이터를 찾아오면 알려주실 정보

- 데이터셋 이름 / 출처 URL.
- 라이선스.
- §4 5가지 체크 결과 (특히 다중 라인 비율).
- 컬럼 목록.
- 파일 위치 (또는 `create_data/raw/`에 둠).

---

## 7. Fallback — 외부 데이터 못 찾을 경우

- **B-1 (현재 합성 보강)** 으로 자동 전환.
- CHANGE-008/009/010/011을 한 번에 처리:
  - co-purchase 페어 주입.
  - 인구×메뉴 prior 주입.
  - `recommendation_events` 합성.
  - 옵션 JSON 합성.
  - validation 보강.
- 보고서엔 "카페 외부 데이터 부재 + 합성 데이터로 시뮬레이션" 정직 기술.

---

## 8. 작업 흐름 (전체 요약)

```
사용자 외부 데이터 검색
  │
  ├─ 발견 ──► §4 검증 통과 ──► §5 통합 순서 (1~6) ──► CF 작동
  │              │
  │              └─ 검증 실패 ──► 다른 후보 검색
  │
  └─ 못 찾음 ──► §7 Fallback (B-1 합성 보강) ──► CF 작동
```
