"""세션 기반 디바운스 + 일일 캡 + IP 기반 Rate Limiter.

- 일반 엔드포인트: 세션당 1초 디바운스 (사용자 피드백 반영).
- 비싼 외부 API 호출(음성/얼굴 분석): 1초 + 세션당 일일 N회 캡.
- /sessions POST: 토큰 발급 전이라 세션 키가 없으므로 IP 기반 분당 캡 적용.
- in-memory 저장 — 단일 인스턴스 운영 전제. 다중 worker 운영 시 Redis 로 교체 필요.
- `/api/v1/logs/batch` 는 로그 손실 방지를 위해 디바운스에서 제외 (호출부에서 의존성 미지정).
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Optional

from fastapi import Header, HTTPException, Request

from core.session_token import session_token_store


class _SessionThrottle:
    def __init__(self) -> None:
        self._last_call: dict[tuple[str, str], float] = {}
        self._daily_count: dict[tuple[str, str, str], int] = defaultdict(int)
        self._lock = asyncio.Lock()

    @staticmethod
    def _day_key() -> str:
        return time.strftime("%Y%m%d", time.gmtime())

    async def debounce(self, session_uuid: str, route_key: str, min_interval: float) -> None:
        if not session_uuid:
            return
        async with self._lock:
            key = (session_uuid, route_key)
            now = time.monotonic()
            last = self._last_call.get(key, 0.0)
            if now - last < min_interval:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": {
                            "code": "TOO_MANY_REQUESTS",
                            "message": f"잠시 후 다시 시도해 주세요.",
                            "details": {"retry_after_ms": int((min_interval - (now - last)) * 1000)},
                        }
                    },
                )
            self._last_call[key] = now

    async def increment_daily(self, session_uuid: str, route_key: str, max_per_day: int) -> None:
        if not session_uuid:
            return
        async with self._lock:
            key = (session_uuid, route_key, self._day_key())
            count = self._daily_count[key] + 1
            if count > max_per_day:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": {
                            "code": "DAILY_QUOTA_EXCEEDED",
                            "message": f"사용 횟수가 일일 한도({max_per_day}회)를 초과했습니다.",
                            "details": {"route": route_key, "limit": max_per_day},
                        }
                    },
                )
            self._daily_count[key] = count


class _IPThrottle:
    """단순 sliding window IP rate limiter. /sessions POST 처럼 세션 키 없는 진입점 보호용."""
    def __init__(self) -> None:
        # ip -> [timestamps within window]
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check(self, ip: str, max_per_window: int, window_sec: float) -> None:
        if not ip:
            return
        async with self._lock:
            now = time.monotonic()
            cutoff = now - window_sec
            recent = [t for t in self._hits[ip] if t > cutoff]
            recent.append(now)
            self._hits[ip] = recent
            if len(recent) > max_per_window:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": {
                            "code": "IP_RATE_LIMIT",
                            "message": "이 IP 에서 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                            "details": {"limit": max_per_window, "window_sec": int(window_sec)},
                        }
                    },
                )


_throttle = _SessionThrottle()
_ip_throttle = _IPThrottle()


def _client_ip(request: Request) -> str:
    """nginx 뒤에서는 X-Real-IP / X-Forwarded-For 가 진짜 클라이언트 IP. 그 외에는 client.host."""
    ip = request.headers.get("x-real-ip")
    if ip:
        return ip.strip()
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def _extract_session_uuid(request: Request, header_session: Optional[str]) -> str:
    """요청에서 session_uuid 를 best-effort 로 추출.
    1) X-Session-UUID 헤더 우선
    2) path param `session_uuid`
    3) query param `session_uuid`
    """
    if header_session:
        return header_session
    path_uuid = request.path_params.get("session_uuid") if request.path_params else None
    if path_uuid:
        return path_uuid
    query_uuid = request.query_params.get("session_uuid")
    if query_uuid:
        return query_uuid
    return ""


def make_debounce(route_key: str, min_interval: float = 1.0, daily_cap: Optional[int] = None):
    """FastAPI Dependency 팩토리 — 세션당 디바운스 + 일일 캡.

    session_uuid 결정 우선순위:
      1) X-Session-Token 으로부터 바인드된 session_uuid (가장 신뢰. body 만 있는 엔드포인트도 보호)
      2) X-Session-UUID 헤더
      3) path / query param

    사용 예시:
        @router.post("/voice/messages", dependencies=[Depends(make_debounce("voice/messages", daily_cap=30))])
    """
    async def _dep(
        request: Request,
        x_session_uuid: Optional[str] = Header(default=None, alias="X-Session-UUID"),
        x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    ) -> None:
        session_uuid = ""
        # 1) 토큰 → 바인드된 session_uuid (body-only 엔드포인트도 이걸로 식별 가능)
        if x_session_token:
            record = session_token_store.validate(x_session_token)
            if record:
                session_uuid = record.session_uuid
        # 2) 헤더 / path / query
        if not session_uuid:
            session_uuid = _extract_session_uuid(request, x_session_uuid)
        if not session_uuid:
            # 세션 키 추출 불가 — /sessions POST 같은 진입점은 통과 (IP throttle 로 별도 보호)
            return
        await _throttle.debounce(session_uuid, route_key, min_interval)
        if daily_cap is not None:
            await _throttle.increment_daily(session_uuid, route_key, daily_cap)

    return _dep


def make_ip_rate_limit(max_per_minute: int = 20, window_sec: float = 60.0):
    """FastAPI Dependency 팩토리 — IP 분당 캡.

    `/sessions POST` 처럼 토큰 발급 전 엔드포인트에 적용. 노출된 API key 가 봇에 의해
    무한 호출되어도 IP 당 분당 N 회로 제한된다.
    """
    async def _dep(request: Request) -> None:
        ip = _client_ip(request)
        await _ip_throttle.check(ip, max_per_minute, window_sec)

    return _dep
