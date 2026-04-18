from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.session import get_session_by_uuid
from model import SessionActivityLog
from schemas import ActivityLogBatchRequest, ActivityLogBatchResponse, make_error


router = APIRouter(prefix="/logs", tags=["Logs"])


@router.post("/batch", response_model=ActivityLogBatchResponse, status_code=status.HTTP_201_CREATED)
async def create_activity_logs(
    req: ActivityLogBatchRequest,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_by_uuid(db, req.session_uuid)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("SESSION_NOT_FOUND", "Session not found", session_uuid=req.session_uuid),
        )

    if not req.events:
        return ActivityLogBatchResponse(session_uuid=req.session_uuid, inserted_count=0)

    logs = [
        SessionActivityLog(
            session_id=session.id,
            seq=event.seq,
            occurred_at=event.occurred_at,
            event_type=event.event_type,
            screen_name=event.screen_name,
            action_name=event.action_name,
            target_type=event.target_type,
            target_id=event.target_id,
            target_label=event.target_label,
            duration_ms=event.duration_ms,
            source=event.source,
            payload_json=event.payload_json,
        )
        for event in sorted(req.events, key=lambda item: (item.seq, item.occurred_at))
    ]

    db.add_all(logs)
    await db.commit()

    return ActivityLogBatchResponse(
        session_uuid=req.session_uuid,
        inserted_count=len(logs),
    )
