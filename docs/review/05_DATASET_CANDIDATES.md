# 외부 데이터 후보 평가 (51개)

> 입력: 별도 AI 조사 결과 51개 후보.
> 본 평가는 시스템 요건(카페/소매 도메인, 다중 라인 주문, 익명화된 사용자/세션 키, 메뉴 카탈로그 매핑 가능성)에 매칭한 결과.
> 모델형 추천이 거부되고 v2 합성 데이터가 채택되어 본 후보 중 직접 사용된 것은 없음. 캡스톤 보고서 references 자료로 보존.

---

## 0. 평가 축

각 데이터셋을 다음 4축으로 평가했다.

| 축 | 의미 |
|---|---|
| **MULTI** | 한 영수증/주문 안에 distinct item ≥ 2 비율. 30% 이상이어야 Item2Vec 학습 가능. |
| **SCALE** | 주문 수 + 메뉴 종수. 주문 5,000건 + 메뉴 30개 이상 권장. |
| **DOMAIN** | 카페/F&B 도메인 거리. 가까울수록 매핑 부담 작음. |
| **ACCESS** | 라이선스/접근성. 공개 무료가 이상적. 유료/회원가입은 감점. |

각 축을 ✅(통과 가능성 높음) / ⚠️(검증 필요) / ❌(부적합)로 표시. 최종 등급은 종합.

---

## 1. 학습 원천(Item2Vec) 후보 — 등급별 분류

### S — 즉시 다운로드 검증 (1순위)

#### 1. Maven Restaurant Orders
- **MULTI**: ✅ 메뉴 한 그릇 단위 주문이 아니라 식사 단위 주문 → 한 주문 다중 라인 가능성 높음.
- **SCALE**: ⚠️ 1분기 데이터, 정확한 수량은 다운로드 후 확인.
- **DOMAIN**: ⚠️ 국제 요리 레스토랑. 메뉴를 카페 카탈로그에 매핑 필요.
- **ACCESS**: ✅ Maven Analytics 공식 무료 (학습용 sample dataset).
- **판단**: **S — 1순위로 다운로드.** order/item 구조가 표준이라 검증 용이.

#### 2. The Bread Basket / Bakery Market Basket
- **MULTI**: ✅✅ 베이커리는 여러 빵·커피·차를 한 번에 사는 구조 → market basket의 표준 예제.
- **SCALE**: ⚠️ 9,000+ transactions, 20,507 entries → 메뉴 종수 적을 가능성. 메뉴 30개 임계 위험.
- **DOMAIN**: ✅✅ 카페·베이커리, 매핑 부담 가장 작음.
- **ACCESS**: ✅ Kaggle 공개.
- **판단**: **S — 1순위.** 메뉴 종수만 확인하면 거의 확정.

### A — 1.5순위 (큰 가능성, 검증 필요)

#### 3. Delivery Hero Recommendation Dataset (DHRD)
- **MULTI**: ✅✅ 4.5M orders, 1M+ users. 다중 라인 표준.
- **SCALE**: ✅✅ 우리 규모 대비 과하게 큼.
- **DOMAIN**: ⚠️ 배달 음식 전체. 카페만 필터링하면 적합하지만 카테고리 라벨 정확도 확인 필요.
- **ACCESS**: ❌⚠️ ACM 논문 발표 데이터셋. 다운로드 권한 확인 필요. 학술용 공개일 가능성 있으나 **신청·승인 절차** 가능성 큼.
- **판단**: **A → S 가능.** 접근 가능 여부가 결정적. 신청해 보고 응답 시점에 따라 1순위 격상.

#### 4. Instacart Market Basket Analysis
- **MULTI**: ✅✅ 3M orders, 한 주문 평균 8~10개 라인.
- **SCALE**: ✅✅ 매우 큼.
- **DOMAIN**: ⚠️ 식료품 잡화. **음료/베이커리/스낵 카테고리만 필터**해야 카페 의미.
- **ACCESS**: ✅ Kaggle 공개. 라이선스는 비상업 학술/캡스톤 OK.
- **판단**: **A — 2순위.** 카페 카테고리 추출 필터링이 추가 작업이지만 학습 효과는 가장 큼.

### B — 보조 학습 데이터

#### 5. Fast Food Sales Report / Balaji Fast Food Sales
- **MULTI**: ⚠️ order_id가 진짜 영수증 단위인지 확인 필수. 패스트푸드는 여러 메뉴 묶음 일반적.
- **SCALE**: ⚠️ 다운로드 후 확인.
- **DOMAIN**: ✅ 음료 + 패스트푸드. 카페 인접.
- **ACCESS**: ✅ Kaggle.
- **판단**: **B → A 가능.** 다중 라인 비율만 통과하면 보조 학습 강력.

#### 6. Dunnhumby Complete Journey
- **MULTI**: ✅ 가구 단위 longitudinal. 한 영수증 다중 라인 표준.
- **SCALE**: ✅ 2,500 households × 2년.
- **DOMAIN**: ⚠️ 식료품 잡화. 카페 인접 카테고리 추출 필요.
- **ACCESS**: ⚠️ Dunnhumby 사이트 가입·다운로드. 학술/비상업 가능.
- **판단**: **B — 인구통계 prior 보강용으로 강력**(CHANGE-010). 학습 원천은 보조.

#### 7. Ta Feng Grocery
- **MULTI**: ✅ market basket 표준.
- **SCALE**: ✅ 817,741 transactions, 23,812 products.
- **DOMAIN**: ⚠️ 식료품. 카페 인접 약함.
- **ACCESS**: ⚠️ 일부 mirror에서 공개. 라이선스 확인.
- **판단**: **B — Item2Vec 안정성 보강용.**

#### 8. Groceries Market Basket Dataset
- **MULTI**: ✅ market basket 표준.
- **SCALE**: ❌ 9,835 transactions, 169 items — 메뉴 종수는 OK이나 주문 수 경계.
- **DOMAIN**: ⚠️ 식료품 일반.
- **ACCESS**: ✅.
- **판단**: **B — 코드 검증/baseline 비교용으로만.**

#### 9. Maven Coffee Shop Sales
- **MULTI**: ❌ `transaction_id`가 라인 단위 unique일 가능성 매우 큼. (이미 우리가 동일 데이터를 `create_data/raw/`에서 사용 중이고, 한 주문 다중 라인 0건임을 확인.)
- **SCALE**: ✅ 149,116 rows.
- **DOMAIN**: ✅✅ 카페 도메인 직접.
- **ACCESS**: ✅ Maven 공식 무료.
- **판단**: **B (학습 원천으로는 부적합)** — 우리가 이미 가지고 있고, 다중 라인 0%로 측정됨. 시간대·인기 메뉴 분석용으로만 유지.

### C — 부적합 또는 보조

#### 10. Café Sales Transactions / Cleaned Cafe Sales
- **MULTI**: ❌ synthetic. 1 transaction = 1 item일 가능성 큼.
- **SCALE**: ⚠️.
- **DOMAIN**: ✅.
- **ACCESS**: ✅.
- **판단**: **C — 전처리 실습용.**

#### 11. Dirty Cafe Sales (10,000 rows synthetic)
- **MULTI**: ❌ synthetic 1줄 단위 가능성 큼.
- **SCALE**: ⚠️.
- **DOMAIN**: ✅.
- **ACCESS**: ✅.
- **판단**: **C — 전처리 실습용. 학습 원천 X.**

#### 12. Restaurant Sales Data (rohitgrewal)
- **MULTI**: ⚠️ 다운로드 후 확인.
- **SCALE**: ⚠️.
- **DOMAIN**: ✅.
- **ACCESS**: ✅.
- **판단**: **C — 우선순위 낮음.**

#### 13. Restaurant Orders Dataset June-July 2025 (550 rows)
- **SCALE**: ❌ 절대 부족.
- **판단**: **D — 폐기.**

#### 14. Restaurant Orders 500 records
- **SCALE**: ❌.
- **판단**: **D — 폐기.**

#### 15. POS Data: Simulated Restaurant Data
- **DATA**: ❌ Faker 합성.
- **판단**: **D — 폐기.**

#### 16. Steakhouse POS Simulated Data
- **DOMAIN/DATA**: ❌.
- **판단**: **D — 폐기.**

#### 17. Fast-Food Restaurant Chain
- **MULTI**: ⚠️ ingredient list 포함 → 다중 라인 가능성.
- **DOMAIN**: ✅.
- **ACCESS**: ⚠️ 라이선스 확인.
- **판단**: **B — 메타데이터 보강 후보.**

#### 18. Food Delivery & Restaurant Sales (60,000 orders)
- **MULTI**: ⚠️ "order log" 형태라면 1 order = 1 row일 위험.
- **DOMAIN**: ⚠️.
- **판단**: **C — 후순위.**

#### 19. Restaurant Delivery Orders (Faker 10,000)
- **DATA**: ❌ synthetic.
- **판단**: **D.**

#### 20. Order Delivery Dataset Talabat (Faker 100,000)
- **DATA**: ❌ synthetic.
- **판단**: **D.**

#### 21. FoodHub Order
- **MULTI**: ⚠️ customer_id, restaurant_name 단위. 한 order에 다중 menu_item 컬럼 있는지 다운로드 후 확인.
- **DOMAIN**: ✅.
- **판단**: **C → B 가능.** 다운로드해서 컬럼만 빠르게 확인 가치.

#### 22. Food Delivery Order History
- **MULTI**: ⚠️.
- **판단**: **C — 후순위.**

#### 23. DoorDash Public/Kaggle delivery
- **DATA**: ❌ delivery delay 분석용.
- **판단**: **D.**

---

## 2. 일반 소매·장바구니 (카페 외 도메인)

| # | 데이터셋 | MULTI | SCALE | DOMAIN | ACCESS | 등급 | 사용처 |
|---|---|---|---|---|---|---|---|
| 24 | Instacart | ✅✅ | ✅✅ | ⚠️ | ✅ | A | 학습 원천 (음료/베이커리 필터) |
| 25 | Dunnhumby | ✅ | ✅ | ⚠️ | ⚠️ | B | 인구통계 prior |
| 26 | Ta Feng | ✅ | ✅ | ⚠️ | ⚠️ | B | 학습 안정성 보강 |
| 27 | Groceries Market Basket | ✅ | ❌ | ⚠️ | ✅ | B | baseline 비교 |
| 28 | UCI Online Retail | ✅ | ✅ | ❌ | ✅ | C | 코드 검증 |
| 29 | UCI Online Retail II | ✅ | ✅ | ❌ | ⚠️ | C | 코드 검증 |
| 30 | Olist Brazilian | ⚠️ | ✅ | ❌ | ✅ | C | 추천 알고리즘 비교용 |
| 31 | RetailRocket | ✅ | ✅ | ❌ | ✅ | C | 알고리즘 비교 |
| 32 | YOOCHOOSE / RecSys2015 | session | ✅ | ❌ | ⚠️ | C | session-based 비교 |
| 33 | Superstore Sales | ⚠️ | ⚠️ | ❌ | ✅ | D | 폐기 |

---

## 3. 콘텐츠/메타데이터 보강

학습 원천 X, 메뉴 메타데이터·콘텐츠 추천·콜드 스타트·보고서 근거에 사용.

| # | 데이터셋 | 사용처 |
|---|---|---|
| 34 | UCI Restaurant & Consumer Data | 식당 추천 비교 (참고) |
| 35 | Entree Chicago | 추천시스템 역사 참고 |
| 36 | Yelp Open Dataset | 카페·식당 리뷰·평점·위치 |
| 37 | Food.com Recipes | 콘텐츠 추천 비교 |
| 38 | Recipe1M+ | 이미지·레시피 임베딩 (오버스펙) |
| 39 | RecipeNLG | 레시피 NLG 참고 |
| 40 | MealRec / MealRec+ | 세트 메뉴/번들 |
| 41 | Amazon Grocery Reviews | CF 알고리즘 비교 |
| 42 | Open Food Facts | 영양·알레르기 메타 |
| 43 | MenuAI / MenuRank | 메뉴 OCR + 영양 ranking |
| 44 | Food-101 | 메뉴 이미지 분류 (오버스펙) |

---

## 4. 국내 카페·상권·공공

| # | 데이터셋 | 사용처 | 비고 |
|---|---|---|---|
| 45 | 아티제 프랜차이즈 카페 판매매출 | **카페 도메인 학습 원천 가능** | 유료/사용 권한 확인 필요. 영수증 단위 다중 라인 여부 확인 필수. |
| 46 | 아티제 카페 매출 데이터 (문화 빅데이터) | 트렌드/요일·채널 분석 | 집계일 가능성 큼. |
| 47 | 마켓링크 커피 판매 | 커피 제품 인기 prior | 유통 데이터, 메뉴 동시구매 약함. |
| 48 | 서울시 상권분석 추정매출 | **인구통계 prior 보강** | 메뉴 없음, 분기 매출만. |
| 49 | 전국카페표준데이터 | 입지/상권 보조 | 주문 없음. |
| 50 | AI Hub 관광 음식메뉴판 | 한국어 메뉴명 정규화 | 학습 원천 X. |
| 51 | AI Hub 음식 이미지/영양정보 | 메뉴 이미지·영양 메타 | 학습 원천 X. |
| (52) | AI Hub 건강관리 음식 이미지 | 보강 메타 | 메뉴 이미지 분류용. |

---

## 5. 다운로드 액션 플랜 (실행 순서)

### Step 1 — 즉시 다운로드 + 검증 (S 등급)
1. **Maven Restaurant Orders** — https://mavenanalytics.io/data-playground/restaurant-orders
2. **The Bread Basket** — Kaggle.

각각 다음 4줄 검증을 돌립니다:

```python
import pandas as pd
df = pd.read_csv("...")
order_col = "order_id"          # 데이터셋마다 다름
item_col  = "item_id"           # 데이터셋마다 다름
multi = df.groupby(order_col)[item_col].nunique()
print("orders >=2 distinct items:", (multi>=2).mean()*100, "%")
print("distinct items total:", df[item_col].nunique())
print("rows:", len(df), "orders:", df[order_col].nunique())
```

**합격 기준**: 다중 라인 30%↑, 메뉴 30개↑.

### Step 2 — 합격 데이터셋이 부족하면 (A 등급 추가)
3. **Instacart Market Basket Analysis** (음료/베이커리 카테고리 필터링 적용).
4. **DHRD 신청 시도** (학술 접근 시도).

### Step 3 — 인구통계 prior 보강 (CHANGE-010 자연 해결)
- **Dunnhumby Complete Journey**: 가구 단위 인구통계 + 장바구니 → 메뉴별 인구통계 prior 학습용.
- **서울시 상권분석 추정매출**: 한국 카페 도메인의 성별·연령·요일별 매출 prior.

### Step 4 — 메뉴 메타데이터 보강 (콜드 스타트 대응)
- **AI Hub 관광 음식메뉴판** (한국어 메뉴명 정규화 사전).
- **Open Food Facts** (영양·알레르기·카페인 등 메타).

### Step 5 — 보고서 근거 (도메인 설득력)
- **Maven Coffee Shop Sales** (이미 보유): 카페 도메인 시간대·인기 메뉴 분석.
- **아티제 카페 판매매출** (접근 가능 시): 한국 프랜차이즈 카페 매출 패턴.

---

## 6. 후보별 차단/주의 사항 요약

### 즉시 폐기 (D)
- 13, 14, 15, 16, 19, 20, 23, 33 — synthetic 또는 규모 부족.

### 우리가 이미 보유 (B로 격하)
- **Maven Coffee Shop Sales (#9)**: `create_data/raw/coffee_shop_sales.xlsx`로 이미 있고, 다중 라인 0% 확인됨. 학습 원천 X, 분석 보조용으로만.

### 접근성 차단 가능성 (보고서에 영향)
- **DHRD (#3)**: 학술 신청 필요.
- **Dunnhumby (#6)**: 사이트 가입·EULA 동의.
- **아티제 매출 (#45, #46)**: 유료/사용 권한 확인.
- **마켓링크 (#47)**: 유료 가능성.

### 라이선스 명시 권장
- 모든 후보에 대해 **CC-BY / Open Database / Kaggle CC0 / 학술 사용 가능** 등 라이선스 문구를 보고서에 인용 형태로 박아둔다.

---

## 7. 결론 — "필요한 데이터" 답

### 7-1. 가장 적합 (1순위 다운로드)
1. **Maven Restaurant Orders**
2. **The Bread Basket**

이 두 개로 Item2Vec 학습이 가능하면 **외부 데이터 활용 시나리오 성립**. 보고서에 "카페·베이커리 도메인 영수증 데이터로 Prod2Vec 학습"으로 기술 가능.

### 7-2. 보강 (2순위)
3. **Instacart** (음료/베이커리 카테고리 필터)
4. **DHRD** (접근 가능 시)
5. **Fast Food Sales Report** (검증 통과 시)

### 7-3. 인구통계 prior (CHANGE-010 자연 해결)
6. **Dunnhumby**
7. **서울시 상권분석 추정매출**

### 7-4. 메뉴 메타·콜드 스타트
8. **AI Hub 관광 음식메뉴판** (한국어 메뉴 매핑)
9. **Open Food Facts** (영양·알레르기)

### 7-5. 보고서 근거
10. **Maven Coffee Shop Sales** (이미 보유, 분석용)
11. **아티제 카페 판매매출** (접근 가능 시)

### 7-6. 폐기/낮은 우선순위
- 13, 14, 15, 16, 19, 20, 23, 33 — 그리고 11, 12, 18, 22, 30, 31, 32 (도메인 거리 + 학습 추가 가치 낮음).

---

## 7-A. 추가 후보 평가 (사용자 발굴)

다음 3개는 사용자가 추가로 발굴한 카페 도메인 후보. 평가 결과:

| # | 데이터셋 | Item2Vec 학습 | 카페 도메인 | 인구통계 | 등급 | 비고 |
|---|---|---|---|---|---|---|
| 52 | [Coffee Sales Dataset (anassarfraz13)](https://www.kaggle.com/datasets/anassarfraz13/coffee-sales-dataset) | ❌ (다중 라인 0% 예상) | ⭐⭐⭐ | ❌ | B/C | 카페 메뉴 prior 검증용 |
| 53 | [Daily Coffee Transactions (minahilfatima12328)](https://www.kaggle.com/datasets/minahilfatima12328/daily-coffee-transactions) | ❌ (집계/1줄 예상) | ⭐⭐⭐ | ❌ | C | 52번과 거의 동일한 한계 |
| 54 | [Starbucks Customer Data (ihormuliar)](https://www.kaggle.com/datasets/ihormuliar/starbucks-customer-data) | ❌ (메뉴 없음) | ⭐⭐⭐ | ⭐⭐⭐ | **A (특수 용도)** | **인구통계 prior 보강 최강 후보** (CHANGE-010 자연 해결) |

### 핵심 발견

세 데이터 모두 **Item2Vec 학습용 다중 메뉴 영수증으로는 부적합 가능성이 높음**. 카페 POS의 일반적 한계.

→ **Item2Vec 메인은 여전히 Bread Basket** (이미 검증, 다중 라인 58.3%).

### 그러나 #54 Starbucks Customer Data는 다른 가치

- 17,000명 실고객의 `gender / age / income / became_member_on` + 30일 거래 패턴.
- **메뉴 없음**이라 Item2Vec엔 못 쓰지만, **인구통계 × 거래 prior**의 실데이터 학습에 최강.
- 우리 합성 데이터의 약점인 "성별·연령대 × 메뉴 선호 상관관계 부재" (CHANGE-010)를 **실데이터로 보강**할 수 있는 유일한 후보.

### 권장 활용 방안

1. **#54 Starbucks Customer Data**: 다운로드 후
   - `profile.json` 인구통계 분포 확인.
   - `transcript.csv`에서 (gender, age) × (hour, day_of_week) × transaction_amount 패턴 추출.
   - 우리 합성 데이터의 인구통계 prior에 반영.
2. **#52 Coffee Sales Dataset**: 다운로드 후 즉시 다중 라인 검증.
   - 0%면 카페 도메인 prior 보조용으로만.
   - >30%면 학습 원천으로도 격상.
3. **#53 Daily Coffee Transactions**: #52 결과에 따라 결정. #52가 부적합이면 동일 폐기.

### 다운로드 검증 결과 (2026-05-04)

#### #52 Coffee Sales Dataset & #53 Daily Coffee Transactions
- **두 데이터셋이 완전히 동일한 파일** (shape/컬럼/내용 100% 일치).
- 3,547 rows / 메뉴 8종 (Americano, Latte, Cappuccino, Cortado, Hot Chocolate, Cocoa, Espresso, Americano with Milk).
- 영수증 그룹 키 없음 (`transaction_id`/`order_id` 부재).
- **분 단위 묶음 다중 라인: 0.5%** — Item2Vec 학습 ❌.
- 시간 단위 묶음 34.3%이지만 의사적이라 신뢰도 낮음.
- **결론**: **#53 폐기 (중복)**, **#52는 카페 시간대·메뉴 인기 prior 보조용**으로만.

#### #54 Starbucks Customer Data
- profile 17,000명, **응답자 14,825명 (87.2%)**.
- transaction 이벤트 138,953건, profile join 후 123,957건.
- 모든 (성별 × 연령대) 묶음에 1,000건+ 표본.
- **메뉴 정보 없음** (transaction.value에 amount만) → Item2Vec ❌.
- **인구통계 × 거래 prior 학습 최강** ⭐⭐⭐.
- **결론**: **확정 채택 (인구통계 prior 보강 전용)**.

### 최종 데이터 구도

| 역할 | 데이터셋 |
|---|---|
| Item2Vec 학습 메인 | Bread Basket ✅ |
| 인구통계 × 거래 prior | Starbucks Customer Data ⭐ |
| 카페 시간대 prior 검증 | Coffee Sales Dataset (1개만 유지) |
| 폐기 (중복) | Daily Coffee Transactions 🗑️ |
| 학습 보강 (선택) | Instacart 음료/베이커리 (추후) |

---

## 7-B. 대용량/Amazon 계열 추가 후보 평가 (사용자 발굴)

### 1순위 장바구니/주문 데이터

| 후보 | 다중 라인 | 도메인 | 인구통계 | 규모 | 결론 |
|---|---|---|---|---|---|
| **Instacart Market Basket Analysis** | ✅✅ | ⚠️ 식료품(음료/베이커리 dept 단독 존재) | ❌ | 3.4M 주문 / 49,685 상품 / 206K users | ⭐ **최우선 추가** — Bread Basket 학습 보강 |
| **Dunnhumby Complete Journey** | ✅ | ⚠️ 식료품 | ✅ household demographic | 2,500 가구 × 2년 | ⭐ **인구통계 prior 보강 후보 2** (Starbucks 다음) |
| JD.com MSOM Challenge | ✅ | ❌ 가전·잡화 | ⚠️ | 2.5M 고객 / 31,868 SKU | 학회 신청 + 도메인 약함 → **폐기** |
| Synerise RecSys 2025 | ⚠️ 행동 로그 | ⚠️ 일반 이커머스 | ❌ | 6개월 1.9GB | 카페 매핑 부담 → **B (시간 여유 시)** |
| Coveo / YOOCHOOSE | ❌ 세션 클릭 | ❌ | ❌ | — | 세션 추천 benchmark — **C (우리 흐름 외)** |

### Amazon 계열

| 후보 | 활용 형태 | 결론 |
|---|---|---|
| **Amazon Reviews 2023** | review-based CF / SASRec — Item2Vec과 호환 X | A지만 우리 결정(Item2Vec)과 다름 → 보류 |
| **SNAP Amazon Co-purchase Metadata** | item-item edge → Node2Vec 임베딩 | A — 그래프 임베딩 비교 부록용 (food/beverage 카테고리만) |
| Amazon Reviews 2018 / SNAP Co-purchase Network | 위의 구버전/유사 | 폐기 |

### 대형 이커머스 행동 로그

| 후보 | 결론 |
|---|---|
| MerRec / RetailRocket / H&M / JDsearch / Taobao / Tmall / Beibei / Diginetica | 카페 도메인 거리 — **C (알고리즘 비교용 / 우리 목적 외)** |

### 광고/CTR

| 후보 | 결론 |
|---|---|
| Criteo / Avazu / iPinYou | CTR 예측 — **D (무관, 폐기)** |

### 기타

| 후보 | 결론 |
|---|---|
| Olist / UCI Online Retail / Online Retail II | 이미 §1·§2에서 C 등급 평가 |
| Rakuten | 상품 분류용 — 폐기 |

### 핵심 결론

대용량 데이터는 많지만, **우리 시스템에 실제 도움 되는 후보는 3개로 좁혀짐**:

1. **Instacart**: Bread Basket과 동일 구조의 다중 라인 영수증 → Item2Vec 학습 보강.
2. **Dunnhumby**: Starbucks가 못 주는 "인구통계 × 메뉴" 페어 신호 부분적 보완.
3. **SNAP Amazon Co-purchase Metadata** (food/beverage만): Node2Vec 임베딩으로 Bread Basket Item2Vec 결과 검증/비교 (부록 수준).

나머지 후보는 카페 도메인과 거리·접근성·우리 결정(Item2Vec)과 호환성 측면에서 우선순위 낮음.

### 최종 데이터 구도 (확정·보강안)

| 역할 | 데이터셋 | 상태 |
|---|---|---|
| Item2Vec 학습 메인 | Bread Basket | ✅ 확정 |
| Item2Vec 학습 보강 | **Instacart (음료/베이커리)** | ⭐ 추가 권장 |
| 인구통계 prior 메인 | Starbucks Customer Data | ✅ 확정 |
| 인구통계 prior 보강 (선택) | **Dunnhumby Complete Journey** | 시간 여유 시 |
| 시간대·메뉴 prior 검증 | Coffee Sales Dataset (1개) | 보조 |
| 그래프 임베딩 부록 비교 (선택) | SNAP Amazon Co-purchase | 학술 비교 |
| 폐기 (중복) | Daily Coffee Transactions | 🗑️ |

---

## 7-C. **최종 채택 (FINAL · 2026-05-04)** — OpenSurvey 자산 발견 후 전면 재정렬

자료조사 폴더에서 OpenSurvey 합성 응답표 + 캡스톤 자체 합성 7종(`rec_*`) 발견 → 데이터 구도 전면 재구성.
(이전 모델 노트북 계획은 모두 REJECTED — 통계 기반 + v2 합성 데이터로 노선 변경. 자세한 결정은 [07_RECOMMENDATION_REWORK_PLAN.md](./07_RECOMMENDATION_REWORK_PLAN.md) 참조.)

### 학습/검증 데이터
| 역할 | 데이터셋 |
|---|---|
| **Item2Vec 학습 메인** | Bread Basket (`create_data/bread basket.csv`) |
| **자체 합성 prior 추출** | `opensurvey_cafe_2025_synthetic.csv` |
| **자체 합성 마스터** | `rec_users.csv`, `rec_items.csv`, `rec_calendar.csv`, `rec_weather_log.csv` |
| **FM 학습 비교 데이터** | `rec_interactions.csv` |

### Reference (외부 검증·보고서 부록)
| 역할 | 데이터셋 |
|---|---|
| 카페 시간대 reference | Coffee Sales Dataset (보유, Phase 1.2 검증용) |
| 글로벌 인구통계 비교 reference | Starbucks Customer Data (보고서 부록) |
| 합성 가설 효과 크기 reference | NIQ Korea / Simon-Kucher / "연령 및 성별 커피 선호" 논문 (자료조사 PDF) |

### 폐기 / 사용 안 함
| 데이터셋 | 사유 |
|---|---|
| Daily Coffee Transactions | Coffee Sales와 동일 파일 (중복) |
| archive (2)/ | Bread Basket 중복 |
| Restaurant_Orders/ | 음료 0개 (도메인 부적합) |
| GACTT (Great American Coffee) | 미국 시음 데이터, 본 모델 학습과 무관 |
| `rec_ml_features.csv` | 자체 인코딩으로 대체 |
| `rec_stores.csv` | 매장 컨텍스트는 1순위 아님, 보류 |
| Instacart / Dunnhumby / SNAP / Maven Restaurant Orders | 본 계획에선 사용 안 함 (불필요) |

### 핵심 변화
- **Item2Vec 학습 보강용 Instacart 다운로드 불필요** — Bread Basket이 카트 페어 신호로 충분.
- **인구통계 prior 메인을 Starbucks → OpenSurvey로 변경** — 한국 시장 직접 매핑.
- **자체 합성 데이터 신규 생성** — `kiosk_sessions.csv`, `kiosk_orders.csv`, `kiosk_order_items.csv` (Phase 1.4).

### 결정 트리

```
Item2Vec 학습 메인 → Bread Basket (확정)
인구통계 prior 보강 → Starbucks Customer Data (#54) 다운로드
카페 도메인 검증 보조 → Coffee Sales Dataset (#52) 다중 라인 확인 후 결정
```

---

## 8. 다음 행동

1. 사용자: Step 1의 두 데이터셋(Maven Restaurant Orders + Bread Basket)을 `create_data/raw/`에 다운로드.
2. 어시스턴트: 5줄짜리 검증 코드를 즉시 실행하여 다중 라인 비율 + 메뉴 종수 + 라이선스 확인 결과를 일자별 작업 로그에 기록.
3. 합격 시: §5 Step 2 진행 (Instacart 카테고리 추출).
4. 부적합 시: 7-2/7-3 순으로 fallback 또는 OpenSurvey 기반 자체 합성으로 전환 (실제 채택안).
