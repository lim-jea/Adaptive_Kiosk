"""
간략화된 트렌드 서비스: Naver DataLab API 기반 트렌드 조회

역할:
1. Naver API에서 지난 7일 검색 트렌드 조회
2. 성별/연령대별 데이터 추출
3. 검색량 비중 → 가중치로 변환 (0.5~2.0)
4. TTL 캐싱으로 API 호출 최소화
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import time

from core.config import settings

logger = logging.getLogger(__name__)


class TrendService:
    """
    Naver DataLab API를 통한 실시간 음료 트렌드 가중치 제공

    - 지난 7일의 검색량을 기반으로 가중치 계산
    - TTL 캐시로 동일 요청 시 API 호출 스킵
    - API 실패 시 기본값(1.0) 반환
    - 유사어(연관어)도 함께 검색하여 정확한 트렌드 반영
    """

    BASE_URL = "https://openapi.naver.com/v1/datalab/search"

    # 음료 유사어 매핑 (음료명 → [기본명, 유사어1, 유사어2, ...])
    # Naver DataLab Crawling config/keyword_batches.json에서 추출
    BEVERAGE_KEYWORDS = {
        # ═══════ 커피 베이스 ═══════
        "에스프레소": [
            "에스프레소", "에스프레소 샷", "에스프레소 마키아또", "룽고", "시그니처 코르타도",
            "espresso", "espresso shot", "espresso macchiato", "lungo", "cortado"
        ],
        "아메리카노": [
            "아메리카노", "아이스 아메리카노", "메가리카노", "빽사이즈 아메리카노",
            "왕할메가커피", "할메가커피", "롱 블랙",
            "americano", "iced americano", "long black", "black coffee"
        ],
        "카페라떼": [
            "카페 라떼", "아이스 라떼", "핫 라떼", "오트 라떼", "플랫 화이트",
            "연유 카페 라떼", "스페니쉬 연유 라떼",
            "cafe latte", "latte", "iced latte", "flat white", "oat latte"
        ],
        "카푸치노": [
            "카푸치노", "카푸치노 커피",
            "cappuccino", "cappuccino coffee"
        ],
        "콜드브루": [
            "콜드 브루", "더치 커피", "나이트로 콜드 브루", "콜드 드립", "오리지널 콜드브루",
            "cold brew", "cold brew coffee", "nitro cold brew", "dutch coffee"
        ],
        "라떼": [  # 카페라떼의 별칭
            "라떼", "카페라떼", "핫 라떼", "아이스 라떼", "스타벅스 라떼"
        ],
        "모카": [  # 달콤한 커피의 일종
            "모카", "카페모카", "핫 모카", "아이스 모카", "카페 모카"
        ],

        # ═══════ 달콤한 커피 ═══════
        "달콤한커피": [
            "바닐라 라떼", "카페 모카", "카라멜 마끼아또", "화이트 초코 라떼", "헤이즐넛 라떼",
            "원조커피", "흑당 라떼", "티라미수 라떼", "토피넛 라떼", "꿀 아메리카노",
            "바닐라 아메리카노",
            "vanilla latte", "cafe mocha", "caramel macchiato", "white chocolate mocha",
            "hazelnut latte", "toffee nut latte"
        ],

        # ═══════ 기타 커피 ═══════
        "콜드브루라떼": [
            "콜드 브루 라떼", "더치 라떼", "나이트로 라떼", "큐브 라떼",
            "cold brew latte", "nitro latte", "cold brew milk latte"
        ],
        "드립커피": [
            "핸드 드립", "드립 커피", "브루드 커피", "푸어 오버", "브루드 커피 오브 더 데이",
            "hand drip", "drip coffee", "brewed coffee", "pour over", "filter coffee"
        ],
        "에스프레소베이스": [
            "에스프레소 베이스", "블랙 커피", "아이스 쉐이큰 에스프레소",
            "헤이즐넛 오트 아이스 쉐이큰 에스프레소",
            "espresso based", "black coffee", "iced shaken espresso"
        ],
        "우유베이스커피": [
            "우유 커피", "밀크 커피", "플랫 화이트", "마키아또", "숏 라떼",
            "milk coffee", "flat white", "latte", "macchiato", "short latte"
        ],
        "아이스크림커피": [
            "아포가토", "커피 플로트", "아이스크림 라떼", "슈크림 라떼", "젤라또 라떼",
            "affogato", "coffee float", "espresso affogato", "ice cream coffee", "gelato latte"
        ],

        # ═══════ 프라푸치노 & 블렌디드 ═══════
        "프라푸치노": [
            "프라푸치노", "블렌디드", "자바 칩 프라푸치노", "카라멜 프라푸치노", "모카 프라푸치노",
            "플랫치노", "커피 프라페",
            "frappuccino", "blended", "java chip frappuccino", "caramel frappuccino",
            "mocha frappuccino", "coffee frappe", "flatccino"
        ],
        "스무디프라페": [
            "스무디", "프라페", "쉐이크", "블렌디드 음료", "프라푸치노", "플랫치노", "퐁크러쉬",
            "smoothie", "frappe", "shake", "frappuccino", "blended drink", "flatccino"
        ],

        # ═══════ 차 & 티 ═══════
        "기본티": [
            "얼 그레이", "잉글리쉬 브렉퍼스트", "캐모마일", "루이보스", "페퍼민트 티",
            "유스베리 티", "히비스커스 블렌드 티", "민트 블렌드 티", "캐모마일 블렌드 티", "아이스 티",
            "earl grey", "english breakfast tea", "chamomile tea", "peppermint tea",
            "rooibos", "youthberry tea", "hibiscus tea", "iced tea"
        ],
        "달콤한티": [
            "밀크 티", "그린티 라떼", "말차 라떼", "말차", "스타벅스 클래식 밀크 티",
            "버블 밀크티", "버블 그린티 라떼", "말차 크림 라떼", "흑당 밀크티 라떼",
            "얼 그레이 바닐라 티 라떼", "런던 포그 티 라떼",
            "milk tea", "matcha latte", "matcha", "bubble milk tea",
            "london fog tea latte", "earl grey vanilla tea latte", "royal milk tea"
        ],
        "티": [  # 일반 티 카테고리
            "캐모마일 티", "얼 그레이 티", "민트 티", "루이보스 티", "복숭아 티",
            "허브 티", "사과 유자차", "허니 자몽 블랙티",
            "chamomile tea", "earl grey tea", "mint tea", "rooibos tea",
            "peach tea", "herbal tea"
        ],
        "우유베이스티": [
            "녹차 라떼", "말차 라떼", "제주 말차 라떼", "밀크 티", "차이 라떼", "런던 포그 라떼",
            "matcha latte", "milk tea", "chai latte", "london fog latte",
            "green tea latte", "jeju matcha latte"
        ],

        # ═══════ 과일 음료 & 에이드 ═══════
        "과일티에이드": [
            "자몽 허니 블랙 티", "유자 민트 티", "복숭아 아이스티", "복숭아 핫 티",
            "허니자몽 블랙티", "오렌지 자몽 티", "애플 민트 티", "허니 레몬 티",
            "달콤 아이스티", "빽사이즈 달콤 아이스티", "유자차",
            "grapefruit honey black tea", "yuzu tea", "peach iced tea",
            "yuzu mint tea", "apple mint tea", "honey lemon tea"
        ],
        "주스에이드": [
            "레몬 에이드", "자몽 에이드", "청포도 에이드", "블루 레몬 에이드", "메가 에이드",
            "체리콕", "라임 모또", "샤인 머스캣 주스", "청포도 유자 레모네이드 리프레셔",
            "피지오", "레몬 피지오",
            "lemonade", "grapefruit ade", "green grape ade", "refresher", "fizzio", "lime mojito"
        ],
        "주스에이드카테고리": [
            "주스", "에이드", "과일 주스", "탄산 에이드", "리프레셔", "피지오",
            "메가 에이드", "체리콕",
            "juice", "ade", "fruit juice", "sparkling ade", "refresher", "fizzio"
        ],

        # ═══════ 스무디 & 쉐이크ㅠ ═══════
        "스무디": [
            "딸기 스무디", "망고 스무디", "바나나 스무디", "요거트 스무디",
            "strawberry smoothie", "mango smoothie", "banana smoothie", "yogurt smoothie"
        ],
        "딸기스무디": [
            "딸기스무디", "딸기 스무디", "스트로베리", "딸기", "딸기 라떼", "딸기 쉐이크",
            "strawberry latte", "strawberry smoothie", "strawberry shake"
        ],
        "망고스무디": [
            "망고스무디", "망고 스무디", "망고", "망고 라떼",
            "mango smoothie", "mango latte", "mango"
        ],
        "논커피스무디": [
            "딸기 라떼", "딸기 스무디", "망고 스무디", "바나나 스무디", "요거트 스무디",
            "퐁크러쉬", "바나나 라떼", "고구마 라떼", "딸기 쉐이크", "바나나 쉐이크", "초코 쉐이크",
            "strawberry latte", "strawberry smoothie", "mango smoothie",
            "banana latte", "yogurt smoothie", "sweet potato latte"
        ],
        "티프라페": [
            "그린티 프라페", "말차 프라페", "딸기 프라페", "망고 프라페", "녹차 프라페",
            "딸기 딜라이트 요거트 블렌디드", "과일 스무디",
            "green tea frappe", "matcha frappe", "strawberry frappe",
            "fruit smoothie blended", "strawberry yogurt blended"
        ],
    }

    def __init__(self):
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET
        self.cache: Dict[str, Tuple[float, float]] = {}  # key → (weight, timestamp)
        self.cache_ttl = settings.TREND_CACHE_TTL or 3600

        if self.client_id and self.client_secret:
            logger.info("✓ Naver Trend Service initialized")
        else:
            logger.warning("Naver API credentials not found. Using default weights.")
    
    def get_weight(
        self,
        beverage_name: str,
        gender: str,
        age_group: str,
        hour_weight: float = 1.0,
    ) -> float:
        """
        음료의 트렌드 가중치 반환
        
        Args:
            beverage_name: 음료명 (예: "아메리카노")
            gender: "M" 또는 "F"
            age_group: "20~29", "30~39", "40~49", "50+"
            hour_weight: 시간대 가중치 (0.5~1.5)
        
        Returns:
            float: 최종 가중치 (0.5 ~ 2.0)
            - 0.5~1.0: 인기도 하강
            - 1.0: 중립 (변화 없음)
            - 1.0~2.0: 인기도 상승
        """
        # 캐시 확인
        cache_key = f"{gender}_{age_group}_{beverage_name}"
        if cache_key in self.cache:
            weight, timestamp = self.cache[cache_key]
            if (time.time() - timestamp) < self.cache_ttl:
                logger.info(f"  [CACHE] {beverage_name} ({gender}/{age_group}): weight={weight:.2f}x (TTL: {self.cache_ttl}s)")
                return weight
        
        # API 호출
        try:
            logger.info(f"  [API_CALL] {beverage_name} ({gender}/{age_group}) - Fetching from Naver...")
            base_weight = self._fetch_from_naver(beverage_name, gender, age_group)
            # 시간대 가중치 적용
            weight = base_weight * hour_weight
            weight = max(0.5, min(2.0, weight))  # 범위 제한
            logger.info(f"  [RESULT] {beverage_name}: base_weight={base_weight:.2f} × hour_weight={hour_weight:.2f} = final={weight:.2f}x")
        except Exception as e:
            logger.warning(f"  [ERROR_FALLBACK] Trend API failed ({beverage_name}): {e}. Using default 1.0")
            weight = 1.0
        
        # 캐시 저장
        self.cache[cache_key] = (weight, time.time())
        return weight
    
    def _fetch_from_naver(self, beverage_name: str, gender: str, age_group: str) -> float:
        """
        Naver API에서 검색 트렌드 조회 후 가중치 계산
        
        Args:
            beverage_name: 음료명
            gender: "M" 또는 "F"
            age_group: "20~29", "30~39", "40~49", "50+"
        
        Returns:
            float: 0.5~2.0 범위의 가중치
        """
        # 1️⃣ API 인증 헤더
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json",
        }
        
        # 2️⃣ 지난 7일 기간
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)
        
        # 3️⃣ 성별/연령대 변환 (백엔드 형식 → Naver 형식)
        naver_gender = "m" if gender == "M" else "f"
        age_map = {
            "20~29": ["3", "4"],
            "30~39": ["5", "6"],
            "40~49": ["7", "8"],
            "50+": ["9", "10", "11"],
        }
        naver_ages = age_map.get(age_group, [])
        
        if not naver_ages:
            raise ValueError(f"Unknown age group: {age_group}")
        
        # 4️⃣ API 요청 본문 (유사어 포함)
        # 음료의 유사어를 가져오고, 없으면 음료명만 사용
        keywords = self.BEVERAGE_KEYWORDS.get(beverage_name, [beverage_name])
        logger.debug(f"  📌 검색 키워드: {keywords}")

        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "timeUnit": "date",
            "keywordGroups": [
                {
                    "groupName": beverage_name,
                    "keywords": keywords  # ← 유사어 포함!
                }
            ],
            "gender": naver_gender,
            "ages": naver_ages,
        }
        
        # 5️⃣ API 호출
        response = requests.post(self.BASE_URL, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        # 6️⃣ 응답 파싱 및 평균 계산
        ratios = []
        for group_result in result.get("results", []):
            for data_point in group_result.get("data", []):
                ratio = data_point.get("ratio", 0)
                if ratio > 0:
                    ratios.append(ratio)
        
        if not ratios:
            logger.warning(f"  No trend data for {beverage_name}")
            return 1.0
        
        # 7️⃣ 평균 계산 및 가중치 변환
        avg_ratio = sum(ratios) / len(ratios)
        
        # 정규화: 50 = 중립(1.0), 0 = 최저(0.5), 100 = 최고(2.0)
        weight = 1.0 + (avg_ratio - 50) / 50.0
        weight = max(0.5, min(2.0, weight))  # 범위 제한
        
        logger.info(
            f"  [CALC] {beverage_name}: "
            f"기간={start_date}~{end_date}, "
            f"지수 {ratios[0]:.0f}~{ratios[-1]:.0f}, "
            f"평균={avg_ratio:.1f} → weight={weight:.2f}x"
        )
        
        return weight


# 싱글톤
_service: Optional[TrendService] = None


def get_trend_service() -> TrendService:
    """싱글톤 인스턴스 반환"""
    global _service
    if _service is None:
        _service = TrendService()
    return _service


def initialize_trend_service() -> bool:
    """트렌드 서비스 초기화 (시작 시 호출)"""
    try:
        service = get_trend_service()
        return service is not None
    except Exception as e:
        logger.error(f"Failed to initialize trend service: {e}")
        return False
