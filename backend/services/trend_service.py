"""
Naver DataLab 기반 트렌드 가중치 서비스.

동작 방식:
1. 서버 시작 시 오늘자 스냅샷 파일이 있으면 로드
2. 없으면 지난 7일~어제 기준으로 한 번만 API 호출해 저장
3. 추천 시에는 메모리 캐시에서만 즉시 조회
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

from core.config import settings

logger = logging.getLogger(__name__)


class TrendService:
    """
    Naver DataLab를 통한 음료 트렌드 가중치 제공.

    - 기준 기간은 항상 서버 날짜 기준 지난 7일 ~ 어제
    - 서버 재시작에도 유지되도록 일자별 스냅샷 파일 저장
    - 추천 시에는 API를 다시 호출하지 않고 메모리 캐시만 사용
    """

    BASE_URL = "https://openapi.naver.com/v1/datalab/search"
    TREND_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "trends"
    SNAPSHOT_PREFIX = "naver_trends"
    SNAPSHOT_RETENTION_DAYS = 7
    FETCH_CONCURRENCY = 4
    TREND_WINDOW_DAYS = 3
    DEMOGRAPHIC_GENDERS = ("M", "F")
    DEMOGRAPHIC_AGES = ("20~29", "30~39", "40~49", "50+")

    # Naver DataLab Crawling config/keyword_batches.json에서 추출
    BEVERAGE_KEYWORDS = {
        "에스프레소": [
            "에스프레소", "에스프레소 샷", "에스프레소 마끼아또", "룽고", "코르타도",
            "espresso", "espresso shot", "espresso macchiato", "lungo", "cortado"
        ],
        "아메리카노": [
            "아메리카노", "아이스 아메리카노", "메가리카노", "빅사이즈 아메리카노",
            "연할메가커피", "연메가커피", "롱 블랙",
            "americano", "iced americano", "long black", "black coffee"
        ],
        "카페라떼": [
            "카페 라떼", "아이스 라떼", "라떼", "스트 라떼", "플랫 화이트",
            "우유 카페 라떼", "스페셜 우유 라떼",
            "cafe latte", "latte", "iced latte", "flat white", "oat latte"
        ],
        "카푸치노": [
            "카푸치노", "카푸치노 커피",
            "cappuccino", "cappuccino coffee"
        ],
        "콜드브루": [
            "콜드 브루", "더치 커피", "헤이즐로 콜드 브루", "콜드 스냅", "오리지널 콜드브루",
            "cold brew", "cold brew coffee", "nitro cold brew", "dutch coffee"
        ],
        "라떼": [
            "라떼", "카페라떼", "바닐라라떼", "아이스 라떼", "스타벅스 라떼"
        ],
        "모카": [
            "모카", "카페모카", "초 모카", "아이스 모카", "카페 모카"
        ],
        "달달커피": [
            "바닐라 라떼", "카페 모카", "카라멜 마끼아또", "화이트 초코 라떼", "헤이즐넛 라떼",
            "연유커피", "흑당 라떼", "티라미수 라떼", "토피넛 라떼", "꿀 아메리카노",
            "바닐라 아메리카노",
            "vanilla latte", "cafe mocha", "caramel macchiato", "white chocolate mocha",
            "hazelnut latte", "toffee nut latte"
        ],
        "콜드브루라떼": [
            "콜드 브루 라떼", "더치 라떼", "헤이즐로 라떼", "말브 라떼",
            "cold brew latte", "nitro latte", "cold brew milk latte"
        ],
        "핸드드립커피": [
            "핸드 드립", "드립 커피", "브루드 커피", "퓨어 오버", "브루드 커피 허브 티",
            "hand drip", "drip coffee", "brewed coffee", "pour over", "filter coffee"
        ],
        "에스프레소베이스": [
            "에스프레소 베이스", "블랙 커피", "아이스 쉐이큰 에스프레소",
            "헤이즐넛 스트 아이스 쉐이큰 에스프레소",
            "espresso based", "black coffee", "iced shaken espresso"
        ],
        "우유베이스커피": [
            "우유 커피", "밀크 커피", "플랫 화이트", "마끼아또", "숏 라떼",
            "milk coffee", "flat white", "latte", "macchiato", "short latte"
        ],
        "아이스크림커피": [
            "아포가토", "커피 플로트", "아이스크림 라떼", "아크림 라떼", "바닐라 라떼",
            "affogato", "coffee float", "espresso affogato", "ice cream coffee", "gelato latte"
        ],
        "프라푸치노": [
            "프라푸치노", "블렌디드", "자바 칩 프라푸치노", "카라멜 프라푸치노", "모카 프라푸치노",
            "플랫치노", "커피 프라페",
            "frappuccino", "blended", "java chip frappuccino", "caramel frappuccino",
            "mocha frappuccino", "coffee frappe", "flatccino"
        ],
        "스무디프라페": [
            "스무디", "프라페", "쉐이크", "블렌디드 음료", "프라푸치노", "플랫치노", "생과일스무디",
            "smoothie", "frappe", "shake", "frappuccino", "blended drink", "flatccino"
        ],
        "기본티": [
            "얼그레이", "잉글리시 브렉퍼스트", "캐모마일", "루이보스", "페퍼민트 티",
            "유스베리 티", "히비스커스 블렌드", "민트 블렌드", "캐모마일 블렌드", "아이스티",
            "earl grey", "english breakfast tea", "chamomile tea", "peppermint tea",
            "rooibos", "youthberry tea", "hibiscus tea", "iced tea"
        ],
        "달달티": [
            "밀크티", "그린티 라떼", "말차 라떼", "말차", "스타벅스 로얄 밀크티",
            "버블 밀크티", "버블 그린티 라떼", "말차 크림 라떼", "흑당 버블티 라떼",
            "얼그레이 바닐라 티 라떼", "런던 포그 티 라떼",
            "milk tea", "matcha latte", "matcha", "bubble milk tea",
            "london fog tea latte", "earl grey vanilla tea latte", "royal milk tea"
        ],
        "티": [
            "캐모마일 티", "얼그레이티", "민트 티", "루이보스 티", "복숭아티",
            "허브 티", "사과 유자차", "허니 자몽 블랙티",
            "chamomile tea", "earl grey tea", "mint tea", "rooibos tea",
            "peach tea", "herbal tea"
        ],
        "우유베이스티": [
            "녹차 라떼", "말차 라떼", "제주 말차 라떼", "밀크티", "차이 라떼", "런던 포그 라떼",
            "matcha latte", "milk tea", "chai latte", "london fog latte",
            "green tea latte", "jeju matcha latte"
        ],
        "과일허브에이드": [
            "자몽 허니 블랙 티", "유자 민트 티", "복숭아 아이스티", "복숭아티",
            "허니자몽 블랙티", "오렌지 민트 티", "애플 민트 티", "허니 레몬 티",
            "사과 아이스티", "빅사이즈 사과 아이스티", "유자차",
            "grapefruit honey black tea", "yuzu tea", "peach iced tea",
            "yuzu mint tea", "apple mint tea", "honey lemon tea"
        ],
        "주스에이드": [
            "레몬 에이드", "자몽 에이드", "청포도에이드", "블루 레몬 에이드", "메가 에이드",
            "체리콕", "라임 모히또", "패션 머스캣 주스", "청포도 유자 레몬에이드 리프레셔",
            "사이다", "레몬 사이다",
            "lemonade", "grapefruit ade", "green grape ade", "refresher", "fizzio", "lime mojito"
        ],
        "주스에이드카테고리": [
            "주스", "에이드", "과일 주스", "탄산 에이드", "리프레셔", "사이다",
            "메가 에이드", "체리콕",
            "juice", "ade", "fruit juice", "sparkling ade", "refresher", "fizzio"
        ],
        "스무디": [
            "딸기 스무디", "망고 스무디", "바나나 스무디", "요거트 스무디",
            "strawberry smoothie", "mango smoothie", "banana smoothie", "yogurt smoothie"
        ],
        "딸기스무디": [
            "딸기스무디", "딸기 스무디", "스트로베리", "딸기", "딸기 라떼", "딸기 에이드",
            "strawberry latte", "strawberry smoothie", "strawberry shake"
        ],
        "망고스무디": [
            "망고스무디", "망고 스무디", "망고", "망고 라떼",
            "mango smoothie", "mango latte", "mango"
        ],
        "과일주스스무디": [
            "딸기 라떼", "딸기 스무디", "망고 스무디", "바나나 스무디", "요거트 스무디",
            "생과일스무디", "바나나 라떼", "고구마 라떼", "딸기 에이드", "바나나 에이드", "초코 에이드",
            "strawberry latte", "strawberry smoothie", "mango smoothie",
            "banana latte", "yogurt smoothie", "sweet potato latte"
        ],
        "티프라페": [
            "그린티 프라페", "말차 프라페", "딸기 프라페", "망고 프라페", "녹차 프라페",
            "딸기 젤라티드 요거트 블렌드", "과일 스무디",
            "green tea frappe", "matcha frappe", "strawberry frappe",
            "fruit smoothie blended", "strawberry yogurt blended"
        ],
    }

    def __init__(self):
        self.enabled = settings.NAVER_TREND_ENABLED
        self.client_id = settings.NAVER_CLIENT_ID
        self.client_secret = settings.NAVER_CLIENT_SECRET
        self.cache: Dict[str, Tuple[float, float]] = {}
        self.persistent_cache: Dict[str, float] = {}
        self.cache_ttl = settings.TREND_CACHE_TTL or 3600
        self.snapshot_metadata: Dict[str, str] = {}
        self._refresh_in_progress = False

        if not self.enabled:
            logger.info("Naver trend integration disabled by env setting.")
        elif self.client_id and self.client_secret:
            logger.info("Naver Trend Service initialized")
        else:
            logger.warning("Naver API credentials not found. Using default weights.")

    def _get_cache_key(self, beverage_name: str, gender: str, age_group: str) -> str:
        return f"{gender}_{age_group}_{beverage_name}"

    def _get_target_date_range(self) -> Tuple[date, date]:
        end_date = datetime.now().date() - timedelta(days=1)
        start_date = end_date - timedelta(days=self.TREND_WINDOW_DAYS - 1)
        return start_date, end_date

    def _get_snapshot_file_path(self, snapshot_date: date) -> Path:
        filename = f"{self.SNAPSHOT_PREFIX}_{snapshot_date.isoformat()}.json"
        return self.TREND_CACHE_DIR / filename

    def _prune_old_snapshot_files(self, today: date) -> None:
        if not self.TREND_CACHE_DIR.exists():
            return

        cutoff = today - timedelta(days=self.SNAPSHOT_RETENTION_DAYS)
        for path in self.TREND_CACHE_DIR.glob(f"{self.SNAPSHOT_PREFIX}_*.json"):
            stem_date = path.stem.replace(f"{self.SNAPSHOT_PREFIX}_", "")
            try:
                snapshot_date = date.fromisoformat(stem_date)
            except ValueError:
                logger.warning("Unexpected trend snapshot filename: %s", path.name)
                continue

            if snapshot_date < cutoff:
                path.unlink(missing_ok=True)
                logger.info("Removed old trend snapshot: %s", path.name)

    def _load_snapshot_if_fresh(self, today: date) -> bool:
        path = self._get_snapshot_file_path(today)
        if not path.exists():
            return False

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to read trend snapshot %s: %s", path.name, exc)
            return False

        start_date, end_date = self._get_target_date_range()
        if (
            payload.get("window_start_date") != start_date.isoformat()
            or payload.get("window_end_date") != end_date.isoformat()
        ):
            logger.info("Trend snapshot window mismatch. Rebuilding today's snapshot.")
            return False

        weights = payload.get("weights", {})
        if not isinstance(weights, dict) or not weights:
            logger.info("Trend snapshot is empty. Rebuilding today's snapshot.")
            return False

        self.persistent_cache = {
            key: float(value)
            for key, value in weights.items()
        }
        self.snapshot_metadata = {
            "snapshot_date": payload.get("snapshot_date", today.isoformat()),
            "window_start_date": payload.get("window_start_date", start_date.isoformat()),
            "window_end_date": payload.get("window_end_date", end_date.isoformat()),
            "generated_at": payload.get("generated_at", ""),
        }
        logger.info(
            "Loaded trend snapshot: %s (%d entries)",
            path.name,
            len(self.persistent_cache),
        )
        return True

    def load_current_snapshot(self) -> int:
        """오늘 기준으로 유효한 스냅샷이 있으면 메모리에 로드한다."""
        if not self.enabled:
            return 0

        today = datetime.now().date()
        self._prune_old_snapshot_files(today)
        if self._load_snapshot_if_fresh(today):
            return len(self.persistent_cache)
        return 0

    def _save_snapshot(self, today: date) -> None:
        self.TREND_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        start_date, end_date = self._get_target_date_range()
        path = self._get_snapshot_file_path(today)
        payload = {
            "snapshot_date": today.isoformat(),
            "window_start_date": start_date.isoformat(),
            "window_end_date": end_date.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "weights": self.persistent_cache,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.snapshot_metadata = {
            "snapshot_date": payload["snapshot_date"],
            "window_start_date": payload["window_start_date"],
            "window_end_date": payload["window_end_date"],
            "generated_at": payload["generated_at"],
        }
        logger.info("Saved trend snapshot: %s", path.name)

    def get_weight(
        self,
        beverage_name: str,
        gender: str,
        age_group: str,
        hour_weight: float = 1.0,
    ) -> float:
        """메모리 캐시에서 트렌드 가중치를 반환한다."""
        if not self.enabled:
            return 1.0

        cache_key = self._get_cache_key(beverage_name, gender, age_group)

        if cache_key in self.persistent_cache:
            weight = self.persistent_cache[cache_key]
            logger.debug(
                "[SNAPSHOT_CACHE] %s (%s/%s): weight=%.2fx",
                beverage_name,
                gender,
                age_group,
                weight,
            )
            return weight * hour_weight

        if cache_key in self.cache:
            weight, timestamp = self.cache[cache_key]
            if (time.time() - timestamp) < self.cache_ttl:
                logger.debug(
                    "[TTL_CACHE] %s (%s/%s): weight=%.2fx",
                    beverage_name,
                    gender,
                    age_group,
                    weight,
                )
                return weight * hour_weight

        logger.debug(
            "[NO_CACHE] %s (%s/%s): using default weight 1.0",
            beverage_name,
            gender,
            age_group,
        )
        return 1.0

    async def ensure_trends_ready(self, menus: List[Dict]) -> int:
        """
        서버 시작 시 오늘자 스냅샷을 로드하거나, 없으면 새로 생성한다.

        Returns:
            캐시된 항목 수
        """
        if not self.enabled:
            return 0

        cached_count = self.load_current_snapshot()
        if cached_count > 0:
            return cached_count

        if self._refresh_in_progress:
            logger.info("Trend precomputation already running in background.")
            return len(self.persistent_cache)

        return await self.precompute_trends(menus, snapshot_date=datetime.now().date())

    async def precompute_trends(
        self,
        menus: List[Dict],
        snapshot_date: Optional[date] = None,
    ) -> int:
        """지난 7일~어제 기준 트렌드 스냅샷을 계산해 저장한다."""
        if not self.enabled:
            return 0

        if not self.client_id or not self.client_secret:
            logger.warning("Naver API credentials not found. Skipping trend precomputation.")
            return 0

        try:
            self._refresh_in_progress = True
            logger.info("Trend precomputation started...")
            start_time = time.time()
            self.persistent_cache = {}

            semaphore = asyncio.Semaphore(self.FETCH_CONCURRENCY)
            tasks = []

            for menu in menus:
                beverage_name = menu.get("name", "")
                if not beverage_name:
                    continue

                for gender in self.DEMOGRAPHIC_GENDERS:
                    for age_group in self.DEMOGRAPHIC_AGES:
                        tasks.append(
                            self._fetch_and_store_weight(
                                semaphore,
                                beverage_name,
                                gender,
                                age_group,
                            )
                        )

            logger.info("Fetching %d trend combinations...", len(tasks))
            results = await asyncio.gather(*tasks, return_exceptions=True)

            success_count = sum(1 for r in results if not isinstance(r, Exception))
            error_count = sum(1 for r in results if isinstance(r, Exception))

            if self.persistent_cache:
                self._save_snapshot(snapshot_date or datetime.now().date())

            elapsed = time.time() - start_time
            logger.info(
                "Trend precomputation completed: success=%d, failed=%d, cached=%d, elapsed=%.2fs",
                success_count,
                error_count,
                len(self.persistent_cache),
                elapsed,
            )
            return len(self.persistent_cache)

        except Exception as exc:
            logger.error("Trend precomputation failed: %s", exc, exc_info=True)
            return 0
        finally:
            self._refresh_in_progress = False

    async def _fetch_and_store_weight(
        self,
        semaphore: asyncio.Semaphore,
        beverage_name: str,
        gender: str,
        age_group: str,
    ) -> float:
        """API 호출 결과를 persistent cache에 저장한다."""
        cache_key = self._get_cache_key(beverage_name, gender, age_group)

        async with semaphore:
            try:
                weight = await asyncio.to_thread(
                    self._fetch_from_naver,
                    beverage_name,
                    gender,
                    age_group,
                )
            except Exception as exc:
                logger.debug(
                    "Trend fetch failed for %s (%s/%s): %s",
                    beverage_name,
                    gender,
                    age_group,
                    exc,
                )
                weight = 1.0

        # 실패 항목도 기본값으로 저장해서 같은 날 재호출을 막는다.
        self.persistent_cache[cache_key] = weight
        return weight

    def _fetch_from_naver(self, beverage_name: str, gender: str, age_group: str) -> float:
        """Naver API에서 지난 7일~어제 검색 트렌드를 조회해 가중치를 계산한다."""
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
            "Content-Type": "application/json",
        }

        start_date, end_date = self._get_target_date_range()

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

        keywords = self.BEVERAGE_KEYWORDS.get(beverage_name, [beverage_name])

        body = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "timeUnit": "date",
            "keywordGroups": [
                {
                    "groupName": beverage_name,
                    "keywords": keywords,
                }
            ],
            "gender": naver_gender,
            "ages": naver_ages,
        }

        response = requests.post(self.BASE_URL, headers=headers, json=body, timeout=30)
        response.raise_for_status()
        result = response.json()

        ratios = []
        for group_result in result.get("results", []):
            for data_point in group_result.get("data", []):
                ratio = data_point.get("ratio", 0)
                if ratio > 0:
                    ratios.append(ratio)

        if not ratios:
            logger.warning("No trend data for %s", beverage_name)
            return 1.0

        avg_ratio = sum(ratios) / len(ratios)
        weight = 1.0 + (avg_ratio - 50) / 50.0
        weight = max(0.5, min(2.0, weight))

        logger.info(
            "[CALC] %s (%s/%s): %s~%s avg=%.1f weight=%.2fx",
            beverage_name,
            gender,
            age_group,
            start_date,
            end_date,
            avg_ratio,
            weight,
        )

        return weight


_service: Optional[TrendService] = None


def get_trend_service() -> TrendService:
    """싱글톤 TrendService 인스턴스를 반환한다."""
    global _service
    if _service is None:
        _service = TrendService()
    return _service


def initialize_trend_service() -> bool:
    """트렌드 서비스 초기화."""
    try:
        if not settings.NAVER_TREND_ENABLED:
            logger.info("Skipping trend service initialization because NAVER_TREND_ENABLED is false.")
            return False
        service = get_trend_service()
        return service is not None
    except Exception as exc:
        logger.error("Failed to initialize trend service: %s", exc)
        return False
