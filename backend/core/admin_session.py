"""관리자 세션 토큰 관리.

관리자 API 키가 sessionStorage 에 평문 저장되어 XSS 시 탈취 가능하던 문제(2-6) 대응.
브라우저는 HttpOnly 쿠키만 보유하므로 자바스크립트가 토큰 값을 읽을 수 없다.

⚠️ in-memory 저장 — 단일 worker 운영 전제. 서버 재시작 시 모든 관리자 세션이 무효화된다.
다중 worker / 다중 인스턴스 운영 시 Redis 로 교체 필요.
"""
from __future__ import annotations

import secrets
import threading
import time

_DEFAULT_TTL_SEC = 30 * 60  # 30분
COOKIE_NAME = "admin_session"


class _AdminSessionStore:
    def __init__(self) -> None:
        self._tokens: dict[str, float] = {}  # token -> expires_at
        self._lock = threading.Lock()

    def issue(self, ttl_sec: int = _DEFAULT_TTL_SEC) -> tuple[str, int]:
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[token] = time.time() + ttl_sec
        return token, ttl_sec

    def validate(self, token: str) -> bool:
        if not token:
            return False
        with self._lock:
            exp = self._tokens.get(token)
            if exp is None:
                return False
            if exp < time.time():
                self._tokens.pop(token, None)
                return False
            return True

    def revoke(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)


admin_session_store = _AdminSessionStore()
