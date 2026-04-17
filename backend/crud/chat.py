"""
chat_messages CRUD.

- 같은 kiosk_session 내에서 여러 번의 채팅 시도를 지원하기 위해
  attempt_started_at으로 그룹을 구분한다.
- 컨텍스트 로드는 메시지 개수가 아니라 누적 글자 수(max_total_chars)로 제한.
"""
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from model import ChatMessage, KioskSession


async def insert_message(
    db: AsyncSession,
    *,
    session_id: int,
    attempt_started_at: datetime,
    role: str,
    content: str,
    purpose: str = "voice_order",
    intent: Optional[str] = None,
    matched_by: Optional[str] = None,
    response_metadata: Optional[dict] = None,
    commit: bool = True,
) -> ChatMessage:
    msg = ChatMessage(
        session_id=session_id,
        attempt_started_at=attempt_started_at,
        purpose=purpose,
        role=role,
        content=content,
        intent=intent,
        matched_by=matched_by,
        response_metadata=response_metadata,
    )
    db.add(msg)
    if commit:
        await db.commit()
        await db.refresh(msg)
    else:
        await db.flush()
    return msg


async def list_messages_for_context(
    db: AsyncSession,
    *,
    session_id: int,
    attempt_started_at: datetime,
    purpose: str = "voice_order",
    max_total_chars: int = 5000,
) -> List[ChatMessage]:
    """
    Gemini 프롬프트에 넣을 이력을 로드한다.

    최신 메시지부터 글자 수를 누적하다가 max_total_chars를 초과하면 멈추고,
    시간순(오름차순)으로 정렬해서 반환한다. 짧은 대화는 그대로,
    긴 대화는 최근 컨텍스트만 살아남게 된다.
    """
    stmt = (
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.attempt_started_at == attempt_started_at,
            ChatMessage.purpose == purpose,
        )
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    # 방어: attempt_started_at이 미세하게 달라져(타임존/초단위 절삭 등)
    # 조회가 0건이 되는 경우가 있다. 이때는 같은 session/purpose의 최신 이력으로 폴백해
    # 모델이 완전히 무(無)컨텍스트로 동작하는 걸 막는다.
    if not rows:
        fallback_stmt = (
            select(ChatMessage)
            .where(
                ChatMessage.session_id == session_id,
                ChatMessage.purpose == purpose,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        )
        rows = (await db.execute(fallback_stmt)).scalars().all()

    selected: List[ChatMessage] = []
    total = 0
    for row in rows:
        total += len(row.content or "")
        if total > max_total_chars and selected:
            break
        selected.append(row)

    selected.reverse()
    return selected


async def list_messages_paginated(
    db: AsyncSession,
    *,
    session_id: int,
    attempt_started_at: Optional[datetime] = None,
    purpose: str = "voice_order",
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[ChatMessage], int]:
    base = select(ChatMessage).where(
        ChatMessage.session_id == session_id,
        ChatMessage.purpose == purpose,
    )
    count_q = select(func.count(ChatMessage.id)).where(
        ChatMessage.session_id == session_id,
        ChatMessage.purpose == purpose,
    )
    if attempt_started_at is not None:
        base = base.where(ChatMessage.attempt_started_at == attempt_started_at)
        count_q = count_q.where(ChatMessage.attempt_started_at == attempt_started_at)

    base = (
        base.order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .offset(skip)
        .limit(limit)
    )
    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(base)).scalars().all()
    return list(rows), total


async def start_new_attempt(
    db: AsyncSession,
    session: KioskSession,
    *,
    persona: Optional[str] = None,
    stage: str = "greeting",
) -> datetime:
    """
    세션 안에서 새로운 음성 주문 시도를 시작한다.
    voice_attempt_started_at을 현재 시각으로 설정하고 stage/persona를 초기화.
    """
    # MySQL DATETIME(0)은 마이크로초를 잘라내므로 비교 실패를 막기 위해
    # 애초에 microsecond를 0으로 맞춰 저장한다.
    now = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    session.voice_attempt_started_at = now
    session.voice_current_stage = stage
    if persona is not None:
        session.voice_persona = persona
    await db.commit()
    await db.refresh(session)
    return now
