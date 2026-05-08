"""설문 응답 CRUD.

핵심 패턴:
  - 세션당 1행 idempotent upsert.
  - 종결 상태(completed/skipped) 가 한 번 굳어지면 더 이상 변경 불가 — 이중 응답 방지.
  - 프론트는 answers/multi_choices/free_texts 를 dict 형태로 보내고, 백엔드가 컬럼별로 분배 저장.
  - 응답 조회 시에는 컬럼들을 다시 dict 형태로 묶어 API 호환성 유지.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from model import KioskSession, SurveyResponse


# ─── 컬럼 매핑 상수 ───────────────────────────────────────────────────────
QUESTION_KEYS: Tuple[str, ...] = tuple(f"q{i}" for i in range(1, 24))  # q1~q23
FREE_TEXT_KEYS: Tuple[str, ...] = (
    "b8_reason", "d1_reason", "e4", "f3", "h2", "i2", "i3",
)
MULTI_KEYS: Tuple[str, ...] = ("f1", "f2", "g1")


async def get_response_by_session_id(
    db: AsyncSession, session_id: int
) -> Optional[SurveyResponse]:
    result = await db.execute(
        select(SurveyResponse).where(SurveyResponse.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def get_session_internal_id(
    db: AsyncSession, session_uuid: str
) -> Optional[int]:
    result = await db.execute(
        select(KioskSession.id).where(KioskSession.session_uuid == session_uuid)
    )
    return result.scalar_one_or_none()


def _apply_answers(response: SurveyResponse, answers: Dict[str, Any]) -> None:
    """answers dict({"q1": {"value": 4, "label": "선호"}, ...}) 를 컬럼별로 분배."""
    for qkey in QUESTION_KEYS:
        entry = answers.get(qkey) if isinstance(answers, dict) else None
        if entry is None:
            setattr(response, f"{qkey}_value", None)
            setattr(response, f"{qkey}_label", None)
            continue
        # entry 는 SurveyAnswerEntry.model_dump 결과 dict
        v = entry.get("value") if isinstance(entry, dict) else None
        label = entry.get("label") if isinstance(entry, dict) else None
        # value 는 정수만 허용 (NPS 0~10 포함, 5단계 1~5)
        try:
            v_int = int(v) if v is not None else None
        except (TypeError, ValueError):
            v_int = None
        setattr(response, f"{qkey}_value", v_int)
        setattr(response, f"{qkey}_label", str(label) if label is not None else None)


def _apply_free_texts(response: SurveyResponse, free_texts: Dict[str, str]) -> None:
    for tkey in FREE_TEXT_KEYS:
        val = free_texts.get(tkey) if isinstance(free_texts, dict) else None
        setattr(response, f"text_{tkey}", val if val else None)


def _apply_multi_choices(
    response: SurveyResponse, multi_choices: Dict[str, List[str]]
) -> None:
    for mkey in MULTI_KEYS:
        items = multi_choices.get(mkey) if isinstance(multi_choices, dict) else None
        setattr(response, f"multi_{mkey}", list(items) if items else [])


def serialize_response(response: SurveyResponse) -> Dict[str, Any]:
    """SurveyResponse ORM → SurveyResponseRead Pydantic 호환 dict."""
    answers: Dict[str, Dict[str, Any]] = {}
    for qkey in QUESTION_KEYS:
        v = getattr(response, f"{qkey}_value", None)
        label = getattr(response, f"{qkey}_label", None)
        if v is None and label is None:
            continue
        entry: Dict[str, Any] = {}
        if v is not None:
            entry["value"] = v
        if label is not None:
            entry["label"] = label
        answers[qkey] = entry

    multi: Dict[str, List[str]] = {
        mkey: list(getattr(response, f"multi_{mkey}", []) or []) for mkey in MULTI_KEYS
    }
    free_texts: Dict[str, str] = {}
    for tkey in FREE_TEXT_KEYS:
        val = getattr(response, f"text_{tkey}", None)
        if val:
            free_texts[tkey] = val

    return {
        "id": response.id,
        "session_id": response.session_id,
        "status": response.status,
        "started_at": response.started_at,
        "completed_at": response.completed_at,
        "duration_ms": response.duration_ms,
        "resp_age": response.resp_age,
        "resp_gender": response.resp_gender,
        "resp_kiosk_freq": response.resp_kiosk_freq,
        "answers": answers,
        "multi_choices": multi,
        "free_texts": free_texts,
        "q7_no_experience": bool(response.q7_no_experience),
        "survey_snapshot": response.survey_snapshot,
        "created_at": response.created_at,
        "updated_at": response.updated_at,
    }


async def upsert_response(
    db: AsyncSession,
    *,
    session_id: int,
    status: str,
    resp_age: Optional[int],
    resp_gender: Optional[str],
    resp_kiosk_freq: Optional[str],
    answers: Dict[str, Any],
    multi_choices: Dict[str, List[str]],
    free_texts: Dict[str, str],
    q7_no_experience: bool,
    survey_snapshot: Optional[str],
    duration_ms: Optional[int],
) -> SurveyResponse:
    """세션당 1행 idempotent 저장. 종결 상태(completed/skipped)는 잠금."""
    existing = await get_response_by_session_id(db, session_id)

    if existing is not None and existing.status in ("completed", "skipped"):
        # 이미 종결됨 — 새 호출은 무시
        return existing

    response = existing or SurveyResponse(session_id=session_id)

    response.status = status
    response.resp_age = resp_age
    response.resp_gender = resp_gender
    response.resp_kiosk_freq = resp_kiosk_freq
    response.q7_no_experience = bool(q7_no_experience)
    response.duration_ms = duration_ms
    if survey_snapshot:
        # 스냅샷은 한 번만 기록(첫 partial 호출에 들어옴) — 이후 호출에서는 덮어쓰지 않음
        if not response.survey_snapshot:
            response.survey_snapshot = survey_snapshot

    _apply_answers(response, answers)
    _apply_free_texts(response, free_texts)
    _apply_multi_choices(response, multi_choices)

    if status in ("completed", "skipped"):
        response.completed_at = datetime.now(timezone.utc)

    if existing is None:
        db.add(response)

    await db.commit()
    await db.refresh(response)
    return response


async def list_responses(
    db: AsyncSession,
    *,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[SurveyResponse], int]:
    base = select(SurveyResponse)
    count_q = select(func.count(SurveyResponse.id))

    if status is not None:
        base = base.where(SurveyResponse.status == status)
        count_q = count_q.where(SurveyResponse.status == status)

    total_result = await db.execute(count_q)
    total = total_result.scalar_one()

    result = await db.execute(
        base.order_by(SurveyResponse.created_at.desc()).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return items, total


async def get_response_summary(db: AsyncSession) -> Dict[str, Any]:
    """관리자 대시보드용 집계."""
    total = (await db.execute(select(func.count(SurveyResponse.id)))).scalar_one()

    status_rows = (
        await db.execute(
            select(SurveyResponse.status, func.count(SurveyResponse.id)).group_by(
                SurveyResponse.status
            )
        )
    ).all()
    status_dist = {str(s): int(c) for s, c in status_rows}

    # 평균 NPS · 평균 전반 만족도 (q23 / q8)
    avg_nps = (
        await db.execute(
            select(func.avg(SurveyResponse.q23_value)).where(
                SurveyResponse.q23_value.is_not(None)
            )
        )
    ).scalar()
    avg_overall = (
        await db.execute(
            select(func.avg(SurveyResponse.q8_value)).where(
                SurveyResponse.q8_value.is_not(None)
            )
        )
    ).scalar()

    return {
        "total": int(total),
        "status_dist": status_dist,
        "avg_nps": float(avg_nps) if avg_nps is not None else None,
        "avg_overall_satisfaction": float(avg_overall) if avg_overall is not None else None,
    }
