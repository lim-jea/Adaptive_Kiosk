"""
추천 통계 배치 프로세스

서버 시작 시 CSV에서 데이터를 로드하여 Mode A/B 통계를 사전 계산합니다.
결과는 메모리 캐시로 저장되어 매번의 추천 요청에서 사용됩니다.

향후 DB 마이그레이션 시: CSV 로드 부분만 DB 쿼리로 변경 (나머지 로직 동일)
"""

import pandas as pd
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class RecommendationBatchProcessor:
    """CSV 기반 추천 통계 사전 계산"""

    # 시간대 정의
    TIME_PERIODS = {
        "morning": (6, 11),      # 06:00 ~ 10:59
        "lunch": (11, 14),       # 11:00 ~ 13:59
        "afternoon": (14, 18),   # 14:00 ~ 17:59
        "evening": (18, 22),     # 18:00 ~ 21:59
        "night": (22, 6),        # 22:00 ~ 05:59 (다음날)
    }

    def __init__(self):
        self.sessions_df: Optional[pd.DataFrame] = None
        self.orders_df: Optional[pd.DataFrame] = None
        self.order_items_df: Optional[pd.DataFrame] = None

    async def precompute_all_stats(self) -> Tuple[Dict, Dict]:
        """
        CSV에서 모든 데이터를 로드하여 Mode A/B 통계 사전 계산

        Returns:
            (stats, metadata) 튜플
            stats: {
                'mode_a': {...},  # Mode A 통계
                'mode_b': {...}   # Mode B 통계
            }
            metadata: {
                'computed_at': '...',
                'sessions_count': ...,
                'orders_count': ...,
                'items_count': ...
            }
        """
        try:
            logger.info("🔄 배치 프로세스 시작: CSV 데이터 로드")
            start_time = datetime.now()

            # 1. CSV 로드
            if not self._load_csv_data():
                logger.error("CSV 데이터 로드 실패")
                return {}, {}

            # 2. Mode A 통계 계산
            logger.info("📊 Mode A 통계 계산 중...")
            mode_a_stats = self._compute_mode_a_stats()

            # 3. Mode B 통계 계산
            logger.info("📊 Mode B 통계 계산 중...")
            mode_b_stats = self._compute_mode_b_stats()

            # 4. 메타데이터
            metadata = {
                "computed_at": start_time.isoformat(),
                "sessions_count": len(self.sessions_df) if self.sessions_df is not None else 0,
                "orders_count": len(self.orders_df) if self.orders_df is not None else 0,
                "items_count": len(self.order_items_df) if self.order_items_df is not None else 0,
                "mode_a_combinations": len(mode_a_stats),
                "mode_b_beverages": len(mode_b_stats),
            }

            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(
                f"✓ 배치 프로세스 완료:\n"
                f"  Mode A 조합: {metadata['mode_a_combinations']}\n"
                f"  Mode B 음료: {metadata['mode_b_beverages']}\n"
                f"  처리 시간: {elapsed_ms:.0f}ms"
            )

            return {"mode_a": mode_a_stats, "mode_b": mode_b_stats}, metadata

        except Exception as e:
            logger.error(f"배치 프로세스 실패: {e}", exc_info=True)
            return {}, {}

    def _load_csv_data(self) -> bool:
        """CSV 데이터 로드"""
        try:
            self.sessions_df = pd.read_csv('./data/kiosk_sessions.csv')
            self.orders_df = pd.read_csv('./data/orders.csv')
            self.order_items_df = pd.read_csv('./data/order_items.csv')

            logger.info(
                f"✓ CSV 로드 완료:\n"
                f"  세션: {len(self.sessions_df):,}\n"
                f"  주문: {len(self.orders_df):,}\n"
                f"  아이템: {len(self.order_items_df):,}"
            )
            return True

        except FileNotFoundError as e:
            logger.error(f"CSV 파일을 찾을 수 없습니다: {e}")
            return False
        except Exception as e:
            logger.error(f"CSV 로드 중 오류: {e}")
            return False

    def _compute_mode_a_stats(self) -> Dict:
        """
        Mode A: 성별×나이대×시간대별 인기 음료 통계

        Returns:
            {
                "gender:M,age:50+,period:morning": {
                    "recommendations": [
                        {"menu_id": 2, "count": 45, "popularity": 0.120},
                        ...
                    ],
                    "total_orders": 380,
                    "total_items": 375,
                    "computed_at": "2026-04-16T03:00:00"
                },
                ...
            }
        """
        try:
            # 시간 추출
            orders_copy = self.orders_df.copy()
            orders_copy['hour'] = pd.to_datetime(orders_copy['created_at']).dt.hour

            # 행 인덱스 기준으로 sessions_df와 병합
            # orders.csv의 session_id (1, 2, 3...) = kiosk_sessions의 행 인덱스(1부터 시작)
            sessions_with_index = self.sessions_df.reset_index(drop=True).reset_index()
            sessions_with_index.columns = ['session_index', 'session_uuid', 'kiosk_id', 'started_at',
                                          'ended_at', 'estimated_gender', 'estimated_age_group',
                                          'end_reason', 'is_simple_mode', 'help_triggered', 'status']
            sessions_with_index['session_id'] = sessions_with_index['session_index'] + 1

            # orders와 sessions 병합
            merged = orders_copy.merge(
                sessions_with_index[['session_id', 'estimated_gender', 'estimated_age_group']],
                on='session_id',
                how='inner'
            )

            # order_items 결합 (order_id는 orders의 행 인덱스 + 1)
            order_items_with_order_id = self.order_items_df.copy()
            merged_with_items = merged.reset_index(drop=True).reset_index()
            merged_with_items.columns = list(merged.columns)
            merged_with_items['order_index'] = merged_with_items.index + 1

            # order_items와 병합
            merged_with_items = merged_with_items.merge(
                order_items_with_order_id,
                left_on='order_index',
                right_on='order_id',
                how='inner'
            )

            # 시간대로 변환
            merged_with_items['period'] = merged_with_items['hour'].apply(self._hour_to_period)

            # 그룹화: 성별 × 나이대 × 시간대 × 음료
            stats = merged_with_items.groupby(
                ['estimated_gender', 'estimated_age_group', 'period', 'menu_id']
            ).size().reset_index(name='count')

            # 캐시 포맷으로 변환
            mode_a_cache = {}

            for (gender, age_group, period), group_data in stats.groupby(
                ['estimated_gender', 'estimated_age_group', 'period']
            ):
                key = f"gender:{gender},age:{age_group},period:{period}"
                total_items = group_data['count'].sum()

                # 음료를 인기도로 정렬
                recommendations = []
                for _, row in group_data.sort_values('count', ascending=False).iterrows():
                    recommendations.append({
                        'menu_id': int(row['menu_id']),
                        'count': int(row['count']),
                        'popularity': round(row['count'] / total_items, 4) if total_items > 0 else 0,
                    })

                # 상위 10개만 유지
                recommendations = recommendations[:10]

                mode_a_cache[key] = {
                    'recommendations': recommendations,
                    'total_orders': len(
                        merged_with_items[
                            (merged_with_items['estimated_gender'] == gender) &
                            (merged_with_items['estimated_age_group'] == age_group) &
                            (merged_with_items['period'] == period)
                        ]['order_index'].unique()
                    ),
                    'total_items': total_items,
                    'computed_at': datetime.now().isoformat(),
                }

            logger.debug(f"  생성된 Mode A 조합: {len(mode_a_cache)}")
            return mode_a_cache

        except Exception as e:
            logger.error(f"Mode A 통계 계산 실패: {e}", exc_info=True)
            return {}

    def _compute_mode_b_stats(self) -> Dict:
        """
        Mode B: 음료×음료 Co-Purchase 통계

        Returns:
            {
                "menu_id:2": {  # 메뉴 2를 선택했을 때
                    "2:3": {"count": 125, "strength": 0.45},    # 음료 2→3 조합
                    "2:15": {"count": 89, "strength": 0.32},    # 음료 2→15 조합
                    ...
                },
                ...
            }
        """
        try:
            # 같은 주문에 있는 음료 조합 찾기
            co_purchases = self.order_items_df.merge(
                self.order_items_df,
                on='order_id',
                suffixes=('_x', '_y')
            )

            # 중복 제거 (A→B와 B→A를 다른 것으로 처리하지 않기)
            co_purchases = co_purchases[
                co_purchases['menu_id_x'] <= co_purchases['menu_id_y']
            ]

            # 자기 자신과의 조합 제거
            co_purchases = co_purchases[co_purchases['menu_id_x'] != co_purchases['menu_id_y']]

            if len(co_purchases) == 0:
                logger.warning("공동 구매 데이터 없음")
                return {}

            # 조합별 빈도 계산
            combo_counts = co_purchases.groupby(['menu_id_x', 'menu_id_y']).size().reset_index(name='count')

            # 메뉴별로 그룹화
            mode_b_cache = {}

            for menu_id in set(combo_counts['menu_id_x'].unique()) | set(combo_counts['menu_id_y'].unique()):
                menu_pairs = combo_counts[
                    (combo_counts['menu_id_x'] == menu_id) |
                    (combo_counts['menu_id_y'] == menu_id)
                ]

                if len(menu_pairs) == 0:
                    continue

                # 이 메뉴의 총 Co-Purchase 수
                menu_total = menu_pairs['count'].sum()

                mode_b_cache[f"menu_id:{menu_id}"] = {}

                for _, row in menu_pairs.iterrows():
                    menu_a = int(row['menu_id_x'])
                    menu_b = int(row['menu_id_y'])
                    count = int(row['count'])

                    # 양방향 모두 저장 (A→B, B→A)
                    if menu_a == menu_id:
                        other_menu = menu_b
                    else:
                        other_menu = menu_a

                    pair_key = f"{min(menu_id, other_menu)}:{max(menu_id, other_menu)}"
                    mode_b_cache[f"menu_id:{menu_id}"][pair_key] = {
                        'count': count,
                        'strength': round(count / menu_total, 4) if menu_total > 0 else 0,
                    }

            logger.debug(f"  생성된 Mode B 메뉴: {len(mode_b_cache)}")
            return mode_b_cache

        except Exception as e:
            logger.error(f"Mode B 통계 계산 실패: {e}", exc_info=True)
            return {}

    def _hour_to_period(self, hour: int) -> str:
        """시간 → 시간대"""
        if 6 <= hour < 11:
            return "morning"
        elif 11 <= hour < 14:
            return "lunch"
        elif 14 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 22:
            return "evening"
        else:
            return "night"


# 싱글톤 인스턴스
_batch_processor: Optional[RecommendationBatchProcessor] = None


def get_batch_processor() -> RecommendationBatchProcessor:
    """배치 프로세서 싱글톤"""
    global _batch_processor
    if _batch_processor is None:
        _batch_processor = RecommendationBatchProcessor()
    return _batch_processor
