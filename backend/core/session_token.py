"""세션 단기 토큰 관리자.

`POST /api/v1/sessions` 시 발급되는 짧은 만료(기본 30분)의 토큰을 in-memory 로 관리한다.
프런트엔드는 발급받은 토큰을 `X-Session-Token` 헤더로 후속 요청에 사용한다.

⚠️ in-memory 저장 — 단일 worker 운영 전제. 서버 재시작 시 모든 토큰이 무효화되며, 프런트엔드는
401 응답을 받으면 새 세션을 생성해야 한다. 다중 worker / 다중 인스턴스 운영 시 Redis 로 교체 필요.

VITE_KIOSK_API_KEY 가 클라이언트 번들에 영구 노출되던 문제(2-3) 의 대체 수단.
백엔드는 당분간 X-API-Key (kiosk 영구키) 또는 X-Session-Token (단기) 둘 다 허용 — 점진적 폐기 경로.
"""
from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

_DEFAULT_TTL_SEC = 30 * 60  # 30분


@dataclass
class _TokenRecord:
    session_uuid: str
    kiosk_id: int
    expires_at: float


class _SessionTokenStore:
    def __init__(self) -> None:
        self._tokens: dict[str, _TokenRecord] = {}
        self._lock = threading.Lock()

    def issue(self, session_uuid: str, kiosk_id: int, ttl_sec: int = _DEFAULT_TTL_SEC) -> tuple[str, int]:
        token = secrets.token_urlsafe(32)
        expires_at = time.time() + ttl_sec
        with self._lock:
            self._tokens[token] = _TokenRecord(
                session_uuid=session_uuid, kiosk_id=kiosk_id, expires_at=expires_at
            )
        return token, ttl_sec

    def validate(self, token: str) -> _TokenRecord | None:
        if not token:
            return None
        with self._lock:
            record = self._tokens.get(token)
            if record is None:
                return None
            if record.expires_at < time.time():
                self._tokens.pop(token, None)
                return None
            return record

    def revoke(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

    def cleanup_expired(self) -> int:
        removed = 0
        now = time.time()
        with self._lock:
            for token, record in list(self._tokens.items()):
                if record.expires_at < now:
                    self._tokens.pop(token, None)
                    removed += 1
        return removed


session_token_store = _SessionTokenStore()
