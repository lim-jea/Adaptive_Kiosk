"""
개선된 추천 서비스: Mode A/B 기반 음료 추천

Mode A: 상황 기반 추천 (gender + age_group + time_period → top 음료)
Mode B: 주문 이력 기반 추천 (selected_beverages → 보완 음료)
"""

import logging
from typing import List, Dict, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from model import Menu
from services.trend_service import get_trend_service

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Mode A/B 추천 엔진
    CSV 데이터 기반 로컬 분석 + DB 메뉴 정보 병합

    캐시 기반 구조:
    - __init__: CSV 로드 (초기화, 메뉴 매핑용)
    - load_cached_stats(): 배치에서 사전 계산한 통계 로드
    - get_mode_a_recommendations(): 캐시 조회 + 트렌드 반영
    - get_mode_b_recommendations(): 캐시 조회
    """

    def __init__(self):
        self.orders_df: Optional[pd.DataFrame] = None
        self.order_items_df: Optional[pd.DataFrame] = None
        self.sessions_df: Optional[pd.DataFrame] = None
        self.is_loaded = False

        # 메뉴 ID 매핑 (캐시)
        self.menu_id_to_name: Dict[int, str] = {}
        self.menu_name_to_id: Dict[str, int] = {}

        # 시간대 가중치 (데이터 기반, 0-23 시간)
        self.hourly_weights: Dict[int, float] = {}

        # 📊 추천 통계 캐시 (배치에서 로드)
        self._mode_a_cache: Dict = {}
        self._mode_b_cache: Dict = {}
        self._stats_metadata: Dict = {}
        self._use_cache = False

        self.load_data()
    
    def load_data(self) -> bool:
        """CSV 데이터 로드 및 시간대 가중치 계산"""
        try:
            self.sessions_df = pd.read_csv('./data/kiosk_sessions.csv')
            self.orders_df = pd.read_csv('./data/orders.csv')
            self.order_items_df = pd.read_csv('./data/order_items.csv')
            
            self.is_loaded = True
            logger.info(
                f"✓ Recommendation engine loaded:"
                f"\n  {len(self.sessions_df):,} sessions, "
                f"{len(self.orders_df):,} orders, "
                f"{len(self.order_items_df):,} items"
            )
            
            # 시간대별 가중치 계산 (CSV 데이터 기반)
            self._calculate_hourly_weights()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to load recommendation data: {e}")
            self.is_loaded = False
            return False
    
    def _calculate_hourly_weights(self):
        """
        CSV 주문 데이터에서 시간대별 가중치 계산
        
        각 시간대의 상대적 주문량에 따라 0.5~1.5 범위의 가중치 생성
        """
        try:
            orders_copy = self.orders_df.copy()
            orders_copy['hour'] = pd.to_datetime(orders_copy['created_at']).dt.hour
            
            # 시간별 주문 건수
            hourly_counts = orders_copy['hour'].value_counts()
            
            if len(hourly_counts) == 0:
                logger.warning("No hourly data found. Using default weights.")
                self.hourly_weights = {h: 1.0 for h in range(24)}
                return
            
            # 정규화: 최대값 = 1.5, 최소값 = 0.5
            max_count = hourly_counts.max()
            min_count = hourly_counts.min()
            range_count = max_count - min_count if max_count > min_count else 1
            
            self.hourly_weights = {}
            for h in range(24):
                count = hourly_counts.get(h, 0)
                if count == 0:
                    weight = 0.5  # 주문 없는 시간
                else:
                    # 정규화: (count - min) / range * 1.0 + 0.5
                    normalized = (count - min_count) / range_count
                    weight = 0.5 + normalized  # 0.5 ~ 1.5
                
                self.hourly_weights[h] = round(weight, 2)
            
            logger.info(
                f"📊 시간대 가중치 계산 완료:"
                f"\n  최소={min(self.hourly_weights.values()):.2f}, "
                f"최대={max(self.hourly_weights.values()):.2f}"
            )
            
        except Exception as e:
            logger.warning(f"Failed to calculate hourly weights: {e}")
            self.hourly_weights = {h: 1.0 for h in range(24)}
    
    def set_menu_mapping(self, menu_id_to_name: Dict[int, str]):
        """DB 메뉴 정보 캐시"""
        self.menu_id_to_name = menu_id_to_name
        self.menu_name_to_id = {v: k for k, v in menu_id_to_name.items()}
        logger.info(f"✓ Menu mapping updated: {len(menu_id_to_name)} menus")
    
    def get_temporal_patterns(self) -> Dict[str, Dict]:
        """
        실제 데이터에서 추출한 시간대/요일별 패턴 반환
        
        Returns:
            {
                'hourly_weights': {0: 0.8, 1: 0.7, ..., 23: 0.95},  # 상대적 가중치
                'daily_weights': {0: 1.0, 1: 0.98, ..., 6: 0.85},   # 요일별 가중치 (0=월, 6=일)
                'peak_hours': [12, 13, 18, 19],                      # 피크 시간
                'peak_days': [0, 1, 2, 3, 4]                        # 평일 (0=월, 4=금)
            }
        """
        if not self.is_loaded:
            return {}
        
        try:
            # 시간대별 주문 분포 계산
            orders_copy = self.orders_df.copy()
            orders_copy['hour'] = pd.to_datetime(orders_copy['created_at']).dt.hour
            orders_copy['day_of_week'] = pd.to_datetime(orders_copy['created_at']).dt.dayofweek
            
            # 시간별 주문 건수
            hourly_counts = orders_copy['hour'].value_counts().sort_index()
            hourly_max = hourly_counts.max()
            hourly_weights = {h: (hourly_counts.get(h, 0) / hourly_max) if hourly_max > 0 else 0.5 
                            for h in range(24)}
            
            # 요일별 주문 건수 (0=월, 6=일)
            daily_counts = orders_copy['day_of_week'].value_counts().sort_index()
            daily_max = daily_counts.max()
            daily_weights = {d: (daily_counts.get(d, 0) / daily_max) if daily_max > 0 else 0.5 
                           for d in range(7)}
            
            # 피크 시간/요일 추출 (상위 30% 이상)
            peak_threshold_hour = hourly_max * 0.7
            peak_threshold_day = daily_max * 0.7
            
            peak_hours = sorted([h for h, cnt in hourly_counts.items() if cnt >= peak_threshold_hour])
            peak_days = sorted([d for d, cnt in daily_counts.items() if cnt >= peak_threshold_day])
            
            # 📊 실제 계산 값만 로깅
            logger.info(
                f"📊 시간대/요일 패턴 분석 완료:"
                f"\n  🕐 시간대 가중치: 최소={min(hourly_weights.values()):.2f}, 최대={max(hourly_weights.values()):.2f}"
                f"\n  📅 요일별 가중치: 최소={min(daily_weights.values()):.2f}, 최대={max(daily_weights.values()):.2f}"
                f"\n  🔝 피크 시간: {peak_hours} (주문 상위 30%)"
                f"\n  🔝 피크 요일: {[self.get_day_of_week_name(d) for d in peak_days]}"
            )
            
            logger.debug(
                f"  📈 시간별 주문 분포: {dict(hourly_counts)}"
            )
            logger.debug(
                f"  📈 요일별 주문 분포: {{{', '.join([f'{self.get_day_of_week_name(d)}: {cnt}' for d, cnt in daily_counts.items()])}}}"
            )
            
            return {
                'hourly_weights': hourly_weights,
                'daily_weights': daily_weights,
                'peak_hours': peak_hours,
                'peak_days': peak_days
            }
        except Exception as e:
            logger.warning(f"Failed to analyze temporal patterns: {e}")
            return {}
    
    def get_day_of_week_name(self, day: int) -> str:
        """요일 번호 → 이름"""
        days = ['월', '화', '수', '목', '금', '토', '일']
        return days[day] if 0 <= day < 7 else 'unknown'
    
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

    # ═══════════════════════════════════════════════════════════════════════
    # 📊 배치 프로세스: CSV 데이터에서 통계 사전 계산
    # ═══════════════════════════════════════════════════════════════════════

    async def precompute_all_stats(self) -> tuple[Dict, Dict]:
        """
        CSV에서 모든 데이터를 로드하여 Mode A/B 통계 사전 계산

        Returns:
            (stats, metadata) 튜플
        """
        try:
            from datetime import datetime

            logger.info("🔄 배치 프로세스 시작: CSV 데이터 로드")
            start_time = datetime.now()

            # 1. CSV 로드
            if not self.is_loaded:
                logger.error("CSV 데이터가 로드되지 않음")
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

    def _compute_mode_a_stats(self) -> Dict:
        """Mode A: 성별×나이대×시간대별 인기 음료 통계"""
        try:
            # 시간 추출 및 타입 변환
            orders_copy = self.orders_df.copy()
            orders_copy['order_id'] = orders_copy.index + 1
            orders_copy['hour'] = pd.to_datetime(orders_copy['created_at']).dt.hour
            orders_copy['session_id'] = pd.to_numeric(orders_copy['session_id'], errors='coerce').fillna(0).astype(int)

            # 행 인덱스 기준으로 sessions_df와 병합
            sessions_with_index = self.sessions_df.reset_index(drop=True)
            sessions_with_index['session_id'] = range(1, len(sessions_with_index) + 1)

            # orders와 sessions 병합
            merged = orders_copy.merge(
                sessions_with_index[['session_id', 'estimated_gender', 'estimated_age_group']],
                on='session_id',
                how='inner'
            )

            # order_items 결합
            merged_with_items = merged.merge(
                self.order_items_df,
                left_on='order_id',
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
                        ]['order_id'].unique()
                    ),
                    'total_items': total_items,
                }

            logger.debug(f"  생성된 Mode A 조합: {len(mode_a_cache)}")
            return mode_a_cache

        except Exception as e:
            logger.error(f"Mode A 통계 계산 실패: {e}", exc_info=True)
            return {}

    def _compute_mode_b_stats(self) -> Dict:
        """Mode B: 음료×음료 Co-Purchase 통계"""
        try:
            # 같은 주문에 있는 음료 조합 찾기
            co_purchases = self.order_items_df.merge(
                self.order_items_df,
                on='order_id',
                suffixes=('_x', '_y')
            )

            # 중복 제거
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

                menu_total = menu_pairs['count'].sum()
                mode_b_cache[f"menu_id:{menu_id}"] = {}

                for _, row in menu_pairs.iterrows():
                    menu_a = int(row['menu_id_x'])
                    menu_b = int(row['menu_id_y'])
                    count = int(row['count'])

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

    def load_cached_stats(self, stats: Dict, metadata: Dict) -> bool:
        """
        배치 프로세스에서 계산한 사전 계산 통계를 로드

        Args:
            stats: {
                'mode_a': {...},  # Mode A 캐시
                'mode_b': {...}   # Mode B 캐시
            }
            metadata: 메타데이터
        """
        try:
            self._mode_a_cache = stats.get('mode_a', {})
            self._mode_b_cache = stats.get('mode_b', {})
            self._stats_metadata = metadata
            self._use_cache = True

            logger.info(
                f"✓ 추천 캐시 로드 완료:\n"
                f"  Mode A: {len(self._mode_a_cache)} 조합\n"
                f"  Mode B: {len(self._mode_b_cache)} 메뉴\n"
                f"  계산 시점: {metadata.get('computed_at', 'N/A')}"
            )
            return True

        except Exception as e:
            logger.error(f"캐시 로드 실패: {e}", exc_info=True)
            self._use_cache = False
            return False

    def get_mode_a_recommendations(
        self,
        gender: str,
        age_group: str,
        hour: int,
        top_n: int = 5,
        include_trend: bool = True
    ) -> Dict:
        """
        Mode A: 상황 기반 추천

        캐시 기반 구조:
        1. 캐시에서 성별×나이×시간대 조합 조회 (매우 빠름)
        2. 트렌드 가중치 실시간 적용 (Naver API)
        3. 최종 스코어 계산 및 순위 반환
        """
        if not self.is_loaded:
            logger.error("Recommendation engine not loaded")
            return {'mode': 'A', 'error': 'Engine not loaded'}

        logger.info(f"🔍 Mode A 추천 요청: gender={gender}, age_group={age_group}, hour={hour}, top_n={top_n}")

        time_period = self._hour_to_period(hour)
        logger.debug(f"  ✓ 시간대 변환: {hour}:00 → {time_period}")

        # 📊 캐시에서 조회 (매우 빠름)
        if self._use_cache:
            cache_key = f"gender:{gender},age:{age_group},period:{time_period}"
            cached_data = self._mode_a_cache.get(cache_key)

            if cached_data:
                logger.debug(f"  ✓ 캐시 히트: {cache_key}")

                # 트렌드 가중치 서비스
                trend_service = get_trend_service() if include_trend else None
                hour_weight = self.hourly_weights.get(hour, 1.0)

                recommendations = []
                for rank, rec in enumerate(cached_data['recommendations'][:top_n], 1):
                    menu_id = rec['menu_id']
                    menu_name = self.menu_id_to_name.get(menu_id, f"Menu_{menu_id}")

                    # 트렌드 가중치 적용
                    trend_weight = 1.0
                    if trend_service:
                        trend_weight = trend_service.get_weight(
                            menu_name, gender, age_group, hour_weight
                        )

                    # 최종 스코어 = 인기도 × 트렌드
                    final_score = rec['popularity'] * trend_weight

                    recommendations.append({
                        'rank': rank,
                        'menu_id': menu_id,
                        'menu_name': menu_name,
                        'count': rec['count'],
                        'popularity': rec['popularity'],
                        'trend_weight': round(trend_weight, 2),
                        'final_score': round(final_score, 3)
                    })

                # 트렌드 가중치로 재정렬
                recommendations.sort(key=lambda x: x['final_score'], reverse=True)
                for i, rec in enumerate(recommendations, 1):
                    rec['rank'] = i

                logger.debug(f"  📊 최종 순위 (트렌드 적용):")
                for rec in recommendations:
                    logger.debug(
                        f"    [{rec['rank']}] {rec['menu_name']}: {rec['final_score']:.3f}"
                    )

                logger.info(f"✅ Mode A 완료 (캐시): {len(recommendations)}개 추천")

                return {
                    'mode': 'A',
                    'situation': f"{gender}/{age_group}/{time_period}",
                    'recommendations': recommendations,
                    'total_orders': cached_data['total_orders'],
                    'total_items': cached_data['total_items'],
                    'cache_hit': True
                }

            else:
                logger.warning(f"  ⚠ 캐시 미스: {cache_key}")
                logger.debug(f"    → 사용 가능한 조합: {list(self._mode_a_cache.keys())[:5]}...")

        # Fallback: CSV 기반 실시간 계산 (캐시 미스 또는 캐시 미활성화)
        logger.debug(f"  🔄 Fallback: CSV 기반 실시간 계산")
        return self._get_mode_a_recommendations_fallback(
            gender, age_group, hour, time_period, top_n, include_trend
        )

    def _get_mode_a_recommendations_fallback(
        self,
        gender: str,
        age_group: str,
        hour: int,
        time_period: str,
        top_n: int,
        include_trend: bool
    ) -> Dict:
        """
        Mode A Fallback: CSV 기반 추천 (캐시 미스 또는 미활성화 시)
        """
        # 해당 상황의 주문 필터링
        session_filtered = self.sessions_df[
            (self.sessions_df['estimated_gender'] == gender) &
            (self.sessions_df['estimated_age_group'] == age_group)
        ]
        logger.debug(f"  ✓ 세션 필터링: {len(session_filtered)}개 세션 매칭")

        if len(session_filtered) == 0:
            logger.warning(f"  ⚠ 매칭된 세션 없음: {gender}/{age_group}")
            return {
                'mode': 'A',
                'situation': f"{gender}/{age_group}/{time_period}",
                'recommendations': [],
                'total_orders': 0,
                'cache_hit': False
            }

        session_ids = session_filtered.index + 1
        filtered = self.orders_df.copy()
        filtered['order_id'] = filtered.index + 1
        filtered = filtered[filtered['session_id'].isin(session_ids)]
        logger.debug(f"  ✓ 대응 주문: {len(filtered)}개")

        # 시간대 필터링
        filtered = filtered.copy()
        filtered['hour'] = pd.to_datetime(filtered['created_at']).dt.hour
        filtered_time = filtered[
            filtered['hour'].apply(self._hour_to_period) == time_period
        ]
        logger.debug(f"  ✓ 시간대 필터링: {len(filtered_time)}개 주문 ({time_period})")

        if len(filtered_time) == 0:
            logger.warning(f"  ⚠ 시간대 필터링 후 결과 없음: {gender}/{age_group}/{time_period}")
            return {
                'mode': 'A',
                'situation': f"{gender}/{age_group}/{time_period}",
                'recommendations': [],
                'total_orders': 0,
                'cache_hit': False
            }

        # 해당 주문의 음료 통계
        orders_in_situation = set(filtered_time['order_id'])
        items_in_situation = self.order_items_df[
            self.order_items_df['order_id'].isin(orders_in_situation)
        ]
        logger.debug(f"  ✓ 음료 아이템: {len(items_in_situation)}개")

        menu_counts = items_in_situation['menu_id'].value_counts()

        # 트렌드 서비스
        trend_service = get_trend_service() if include_trend else None
        hour_weight = self.hourly_weights.get(hour, 1.0)

        recommendations = []
        for rank, (menu_id, count) in enumerate(menu_counts.head(top_n).items(), 1):
            menu_id = int(menu_id)
            menu_name = self.menu_id_to_name.get(menu_id, f"Menu_{menu_id}")

            # 인기도 계산
            popularity = count / len(items_in_situation)

            # 트렌드 가중치
            trend_weight = 1.0
            if trend_service:
                trend_weight = trend_service.get_weight(menu_name, gender, age_group, hour_weight)

            # 최종 스코어
            final_score = popularity * trend_weight

            recommendations.append({
                'rank': rank,
                'menu_id': menu_id,
                'menu_name': menu_name,
                'count': int(count),
                'popularity': round(popularity, 3),
                'trend_weight': round(trend_weight, 2),
                'final_score': round(final_score, 3)
            })

        # 최종 스코어로 재정렬
        recommendations.sort(key=lambda x: x['final_score'], reverse=True)

        logger.debug(f"  📊 최종 순위 (트렌드 적용 후):")
        for i, rec in enumerate(recommendations, 1):
            rec['rank'] = i
            logger.debug(
                f"    [{rec['rank']}] {rec['menu_name']}: {rec['final_score']:.3f}"
            )

        logger.info(f"✅ Mode A 완료 (Fallback): {len(recommendations)}개 추천")

        return {
            'mode': 'A',
            'situation': f"{gender}/{age_group}/{time_period}",
            'recommendations': recommendations,
            'total_orders': len(orders_in_situation),
            'total_items': len(items_in_situation),
            'cache_hit': False
        }
    
    def get_mode_b_recommendations(
        self,
        selected_menu_ids: List[int],
        top_n: int = 5,
        include_trend: bool = False
    ) -> Dict:
        """
        Mode B: 주문 이력 기반 추천 (보완 음료)

        캐시 기반 구조:
        1. 선택한 음료별로 캐시에서 Co-Purchase 데이터 조회
        2. 모든 선택 음료의 Co-Purchase 결과를 합산
        3. 빈도순으로 보완 음료 추천
        """
        if not self.is_loaded:
            logger.error("Recommendation engine not loaded")
            return {'mode': 'B', 'error': 'Engine not loaded'}

        logger.info(f"🔍 Mode B 추천 요청: selected_menu_ids={selected_menu_ids}, top_n={top_n}")

        selected_set = set(selected_menu_ids)
        selected_names = [self.menu_id_to_name.get(mid, f"Menu_{mid}") for mid in selected_menu_ids]
        logger.debug(f"  ✓ 선택된 음료: {', '.join(selected_names)}")

        # 📊 캐시에서 조회 (매우 빠름)
        if self._use_cache:
            complementary_dict = {}  # {menu_id: count}

            for selected_id in selected_menu_ids:
                cache_key = f"menu_id:{selected_id}"
                cached_pairs = self._mode_b_cache.get(cache_key)

                if cached_pairs:
                    logger.debug(f"  ✓ 캐시 히트: {cache_key} ({len(cached_pairs)}개 쌍)")

                    # 이 메뉴의 모든 Co-Purchase 쌍 수집
                    for pair_key, stats in cached_pairs.items():
                        count = stats['count']

                        # Pair_key는 "min:max" 형식, 반대쪽 메뉴 찾기
                        parts = pair_key.split(':')
                        menu_a, menu_b = int(parts[0]), int(parts[1])
                        other_menu = menu_b if menu_a == selected_id else menu_a

                        # 이미 선택된 음료는 제외
                        if other_menu not in selected_set:
                            complementary_dict[other_menu] = complementary_dict.get(other_menu, 0) + count

                else:
                    logger.debug(f"  ⚠ 캐시 미스: {cache_key}")

            if complementary_dict:
                logger.debug(f"  ✓ 보완 음료 후보: {len(complementary_dict)}종류")

                recommendations = []
                for rank, (menu_id, total_count) in enumerate(
                    sorted(complementary_dict.items(), key=lambda x: x[1], reverse=True)[:top_n],
                    1
                ):
                    menu_name = self.menu_id_to_name.get(menu_id, f"Menu_{menu_id}")
                    strength = total_count / sum(complementary_dict.values())

                    logger.debug(f"    [{rank}] {menu_name}: count={total_count}, strength={strength:.1%}")

                    recommendations.append({
                        'rank': rank,
                        'menu_id': menu_id,
                        'menu_name': menu_name,
                        'copurchase_count': int(total_count),
                        'strength': round(strength, 3),
                        'frequency': f"{strength*100:.1f}%"
                    })

                logger.info(f"✅ Mode B 완료 (캐시): {len(recommendations)}개 보완 음료 추천")

                return {
                    'mode': 'B',
                    'selected': [
                        {
                            'menu_id': mid,
                            'menu_name': self.menu_id_to_name.get(mid, f"Menu_{mid}")
                        }
                        for mid in selected_menu_ids
                    ],
                    'recommendations': recommendations,
                    'ordered_with': sum(complementary_dict.values()),
                    'cache_hit': True
                }

            else:
                logger.warning(f"  ⚠ 캐시에서 보완 음료 찾을 수 없음")

        # Fallback: CSV 기반 실시간 계산
        logger.debug(f"  🔄 Fallback: CSV 기반 실시간 계산")
        return self._get_mode_b_recommendations_fallback(selected_menu_ids, selected_set, top_n)

    def _get_mode_b_recommendations_fallback(
        self,
        selected_menu_ids: List[int],
        selected_set: set,
        top_n: int
    ) -> Dict:
        """
        Mode B Fallback: CSV 기반 추천 (캐시 미스 또는 미활성화 시)
        """
        # 선택한 음료가 포함된 주문 찾기
        orders_with_selected = self.order_items_df[
            self.order_items_df['menu_id'].isin(selected_set)
        ]['order_id'].unique()

        logger.debug(f"  ✓ 선택 음료 포함 주문: {len(orders_with_selected)}개")

        if len(orders_with_selected) == 0:
            logger.warning(f"  ⚠ 선택 음료가 포함된 주문 없음")
            return {
                'mode': 'B',
                'selected': [
                    {
                        'menu_id': mid,
                        'menu_name': self.menu_id_to_name.get(mid, f"Menu_{mid}")
                    }
                    for mid in selected_menu_ids
                ],
                'recommendations': [],
                'ordered_with': 0,
                'cache_hit': False
            }

        # 같은 주문에 포함된 다른 음료 수집
        items_in_orders = self.order_items_df[
            self.order_items_df['order_id'].isin(orders_with_selected)
        ]
        logger.debug(f"  ✓ 해당 주문의 총 아이템: {len(items_in_orders)}개")

        complementary_counts = Counter()
        for menu_id in items_in_orders['menu_id'].unique():
            if menu_id not in selected_set:
                count = len(items_in_orders[items_in_orders['menu_id'] == menu_id])
                complementary_counts[menu_id] += count

        logger.debug(f"  ✓ 보완 음료 후보: {len(complementary_counts)}종류")

        recommendations = []
        for rank, (menu_id, count) in enumerate(complementary_counts.most_common(top_n), 1):
            menu_id = int(menu_id)
            menu_name = self.menu_id_to_name.get(menu_id, f"Menu_{menu_id}")
            strength = count / len(orders_with_selected)

            logger.debug(f"    [{rank}] {menu_name}: count={count}, strength={strength:.1%}")

            recommendations.append({
                'rank': rank,
                'menu_id': menu_id,
                'menu_name': menu_name,
                'copurchase_count': int(count),
                'strength': round(strength, 3),
                'frequency': f"{strength*100:.1f}%"
            })

        logger.info(f"✅ Mode B 완료 (Fallback): {len(recommendations)}개 보완 음료 추천")

        return {
            'mode': 'B',
            'selected': [
                {
                    'menu_id': mid,
                    'menu_name': self.menu_id_to_name.get(mid, f"Menu_{mid}")
                }
                for mid in selected_menu_ids
            ],
            'recommendations': recommendations,
            'ordered_with': len(orders_with_selected),
            'cache_hit': False
        }

    # ═══════════════════════════════════════════════════════════════════════
    # 🤝 협업 필터링 (CF) 중심 통합 추천
    # ═══════════════════════════════════════════════════════════════════════

    def _get_global_popularity(self, menu_id: int) -> float:
        """
        전체 사용자의 평균 인기도 (모든 Mode A 조합에서의 평균)

        Args:
            menu_id: 메뉴 ID

        Returns:
            0~1 범위의 전체 평균 인기도
        """
        if not self._use_cache or not self._mode_a_cache:
            logger.warning(f"Global popularity cache not available for menu {menu_id}")
            return 0.5  # 기본값: 중립적 인기도

        total_popularity = 0.0
        count = 0

        for cache_data in self._mode_a_cache.values():
            recommendations = cache_data.get('recommendations', [])
            for rec in recommendations:
                if rec['menu_id'] == menu_id:
                    total_popularity += rec['popularity']
                    count += 1

        if count == 0:
            logger.debug(f"  Menu {menu_id} not found in any Mode A combination")
            return 0.0

        global_popularity = total_popularity / count
        logger.debug(f"  Global popularity for menu {menu_id}: {global_popularity:.4f} ({count} combinations)")
        return round(global_popularity, 4)

    def get_cf_score(
        self,
        menu_id: int,
        profile_popularity: float,
        global_popularity: float
    ) -> float:
        """
        CF 점수 계산: 0.6 × profile + 0.4 × global

        Args:
            menu_id: 메뉴 ID (로깅용)
            profile_popularity: 같은 프로필 사용자의 인기도
            global_popularity: 전체 사용자의 평균 인기도

        Returns:
            CF 종합 점수 (0~1)
        """
        cf_score = 0.6 * profile_popularity + 0.4 * global_popularity
        logger.debug(
            f"  CF Score for menu {menu_id}: {cf_score:.4f} "
            f"(profile=0.6×{profile_popularity:.3f}, global=0.4×{global_popularity:.3f})"
        )
        return round(cf_score, 4)

    def _get_cart_candidate_menu_ids(self, cart_items: List[int]) -> set[int]:
        """장바구니와 함께 자주 주문된 메뉴 후보를 수집한다."""
        candidate_ids: set[int] = set()

        for selected_id in cart_items:
            cached_pairs = self._mode_b_cache.get(f"menu_id:{selected_id}", {})
            for pair_key in cached_pairs.keys():
                menu_a, menu_b = map(int, pair_key.split(':'))
                other_menu = menu_b if menu_a == selected_id else menu_a
                if other_menu not in cart_items:
                    candidate_ids.add(other_menu)

        return candidate_ids

    def _get_cart_cf_score(self, candidate_menu_id: int, cart_items: List[int]) -> float:
        """
        장바구니 기반 item-item CF 점수.

        평균만 내면 메뉴가 많아질수록 점수가 희석되므로,
        가장 강한 연결을 중심으로 보되 여러 장바구니 메뉴와 동시에
        연결될 때는 소폭 보너스를 준다.
        """
        if not cart_items:
            return 0.0

        strengths: List[float] = []

        for selected_id in cart_items:
            cached_pairs = self._mode_b_cache.get(f"menu_id:{selected_id}", {})
            if not cached_pairs:
                continue

            pair_key = f"{min(selected_id, candidate_menu_id)}:{max(selected_id, candidate_menu_id)}"
            pair_stats = cached_pairs.get(pair_key)
            if pair_stats:
                strengths.append(float(pair_stats.get('strength', 0.0)))

        if not strengths:
            return 0.0

        strongest_link = max(strengths)
        avg_link = sum(strengths) / len(strengths)
        coverage_bonus = min(0.03, 0.01 * (len(strengths) - 1))

        # 강한 연결을 우선하면서, 여러 메뉴와 동시에 연결될 때만 약하게 가산
        cart_cf_score = (strongest_link * 0.75) + (avg_link * 0.25) + coverage_bonus
        return round(cart_cf_score, 4)

    def get_integrated_recommendations(
        self,
        gender: str,
        age: int,
        cart_items: Optional[List[int]] = None,
        top_n: int = 5,
        include_trend: bool = True
    ) -> Dict:
        """
        협업 필터링(CF) 중심 통합 추천

        알고리즘:
        1. 나이 → 나이대 변환
        2. 시간 → 시간대 변환
        3. 모든 음료에 대해:
           a. Profile popularity: Mode A 캐시에서 조회
           b. Global popularity: 모든 Mode A에서의 평균
           c. CF_Score = 0.6×profile + 0.4×global
           d. 트렌드 가중치 적용 (선택사항)
           e. Final_Score = CF_Score + (Trend×0.15)
        4. 장바구니 음료는 제외
        5. 상위 N개 반환

        Args:
            gender: M 또는 F
            age: 15~100 (나이)
            cart_items: 장바구니 음료 menu_id 목록 (기본: 빈 리스트)
            top_n: 추천 개수 (기본: 5)
            include_trend: 트렌드 반영 여부 (기본: True)

        Returns:
            {
                'mode': 'CF',
                'user_context': {...},
                'cart_items': [...],
                'recommendations': [...],
                'cache_hit': bool
            }
        """
        from utils.recommendation_utils import age_to_age_group
        from datetime import datetime

        if not self.is_loaded:
            logger.error("Recommendation engine not loaded")
            return {'mode': 'CF', 'error': 'Engine not loaded'}

        cart_items = cart_items or []
        logger.info(f"🔍 CF 추천 요청: gender={gender}, age={age}, cart={cart_items}, top_n={top_n}")

        try:
            # 1. 나이 → 나이대 변환
            try:
                age_group = age_to_age_group(age)
            except ValueError as e:
                logger.warning(f"Age validation failed: {e}")
                return {'mode': 'CF', 'error': str(e)}

            # 2. 시간 → 시간대 변환
            current_hour = datetime.now().hour
            period = self._hour_to_period(current_hour)
            logger.debug(f"  ✓ Conversion: age={age} → age_group={age_group}, hour={current_hour} → period={period}")

            # 3. Profile popularity 조회 (Mode A 캐시)
            cache_key = f"gender:{gender},age:{age_group},period:{period}"
            profile_data = self._mode_a_cache.get(cache_key) if self._use_cache else None

            if not profile_data:
                logger.warning(f"  ⚠ Profile not found in cache: {cache_key}")
                return {
                    'mode': 'CF',
                    'error': f'No data for profile: {gender}/{age_group}/{period}'
                }

            logger.debug(f"  ✓ Cache hit: {cache_key}")

            # 모든 메뉴별 CF 점수 계산
            profile_popularity_map = {
                rec['menu_id']: rec['popularity']
                for rec in profile_data['recommendations']
            }
            candidate_menu_ids = set(profile_popularity_map.keys())
            if cart_items:
                candidate_menu_ids.update(self._get_cart_candidate_menu_ids(cart_items))

            cf_scores = {}
            for menu_id in candidate_menu_ids:
                profile_pop = profile_popularity_map.get(menu_id, 0.0)
                global_pop = self._get_global_popularity(menu_id)
                base_cf_score = self.get_cf_score(menu_id, profile_pop, global_pop)
                cart_cf_score = self._get_cart_cf_score(menu_id, cart_items)

                if cart_items:
                    # 장바구니가 있을 때는 item-based CF를 더 우선하되,
                    # 프로필 기반 추천이 완전히 사라지지 않도록 균형 유지
                    cf_score = round((base_cf_score * 0.35) + (cart_cf_score * 0.65), 4)
                else:
                    cf_score = base_cf_score

                cf_scores[menu_id] = {
                    'profile_popularity': profile_pop,
                    'global_popularity': global_pop,
                    'cart_cf_score': cart_cf_score,
                    'cf_score': cf_score,
                }

            # 4. 트렌드 가중치 적용
            trend_service = get_trend_service() if include_trend else None
            hour_weight = self.hourly_weights.get(current_hour, 1.0)

            recommendations = []
            for menu_id, scores in cf_scores.items():
                # 장바구니에 있는 음료는 제외
                if menu_id in cart_items:
                    logger.debug(f"  Skipping menu {menu_id} (in cart)")
                    continue

                menu_name = self.menu_id_to_name.get(menu_id, f"Menu_{menu_id}")

                # 트렌드 가중치
                trend_score = 1.0
                if trend_service:
                    trend_score = trend_service.get_weight(
                        menu_name, gender, age_group, hour_weight
                    )

                # Final Score = CF_Score + (Trend × 0.15)
                final_score = scores['cf_score'] + (trend_score * 0.15)

                reasoning = (
                    f"Profile({age_group}/{period}): {scores['profile_popularity']:.3f}, "
                    f"Global: {scores['global_popularity']:.3f}, "
                    f"CartCF: {scores['cart_cf_score']:.3f}, "
                    f"Trend: {trend_score:.2f}"
                )

                recommendations.append({
                    'rank': len(recommendations) + 1,
                    'menu_id': menu_id,
                    'menu_name': menu_name,
                    'cf_breakdown': {
                        'profile_popularity': round(scores['profile_popularity'], 4),
                        'global_popularity': round(scores['global_popularity'], 4),
                        'cart_cf_score': round(scores['cart_cf_score'], 4),
                        'cf_score': round(scores['cf_score'], 4)
                    },
                    'trend_score': round(trend_score, 2),
                    'final_score': round(final_score, 4),
                    'reasoning': reasoning
                })

            # 5. Final Score로 정렬 및 상위 N개 선택
            recommendations.sort(key=lambda x: x['final_score'], reverse=True)
            recommendations = recommendations[:top_n]

            # 순위 재설정
            for i, rec in enumerate(recommendations, 1):
                rec['rank'] = i

            logger.debug(f"  📊 최종 추천 (top {len(recommendations)}):")
            for rec in recommendations:
                logger.debug(
                    f"    [{rec['rank']}] {rec['menu_name']}: {rec['final_score']:.4f}"
                )

            # 6. 장바구니 음료 정보 추가
            cart_item_list = []
            for cart_id in cart_items:
                cart_item_list.append({
                    'menu_id': cart_id,
                    'menu_name': self.menu_id_to_name.get(cart_id, f"Menu_{cart_id}")
                })

            logger.info(f"✅ CF 추천 완료: {len(recommendations)}개 추천")

            return {
                'mode': 'CF',
                'user_context': {
                    'gender': gender,
                    'age_group': age_group,
                    'period': period,
                    'current_hour': current_hour
                },
                'cart_items': cart_item_list,
                'recommendations': recommendations,
                'cache_hit': profile_data is not None
            }

        except Exception as e:
            logger.error(f"CF 추천 실패: {e}", exc_info=True)
            return {'mode': 'CF', 'error': str(e)}


# 싱글톤 인스턴스
_engine: Optional[RecommendationEngine] = None


def get_recommendation_engine() -> RecommendationEngine:
    """싱글톤 추천 엔진 인스턴스 반환"""
    global _engine
    if _engine is None:
        _engine = RecommendationEngine()
    return _engine


async def initialize_recommendation_engine(db: AsyncSession) -> bool:
    """서버 시작 시 호출 - 메뉴 정보 캐시"""
    engine = get_recommendation_engine()
    
    if not engine.is_loaded:
        logger.warning("Recommendation engine not loaded")
        return False
    
    try:
        # 모든 메뉴 조회
        stmt = select(Menu).where(Menu.is_available == True)
        result = await db.execute(stmt)
        menus = result.scalars().all()
        
        menu_id_to_name = {m.id: m.name for m in menus}
        engine.set_menu_mapping(menu_id_to_name)
        logger.info(f"✓ Menu mapping cached: {len(menu_id_to_name)} menus")
        return True
    
    except Exception as e:
        logger.error(f"Failed to initialize menu mapping: {e}")
        return False
