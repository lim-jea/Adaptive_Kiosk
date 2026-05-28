"""설문 응답 라우터.

POST /api/v1/survey/responses
    프론트가 섹션 이동·완료·스킵 시점마다 호출. session_uuid 기반 idempotent upsert.
    한 번 종결(completed/skipped)되면 같은 세션의 추가 호출은 무시되고 기존 응답을 반환.

GET /api/v1/admin/survey/responses
    관리자 인증 필요. 페이지네이션 + 상태 필터.

GET /api/v1/admin/survey/summary
    관리자 인증 필요. 응답 수와 상태 분포 집계.

GET /api/v1/survey/codebook
    문항 코드북(JSON) 정적 반환. 프론트가 단일 진실원으로 참조.
"""
import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from core.session_auth import assert_token_matches_session
from crud.survey import (
    get_response_summary,
    get_session_internal_id,
    list_responses,
    serialize_response,
    upsert_response,
)
from schemas import (
    PaginatedResponse,
    SurveyListRequest,
    SurveyResponseRead,
    SurveyResponseUpsertRequest,
    make_error,
)

router = APIRouter(prefix="/survey", tags=["Survey"])
admin_router = APIRouter(prefix="/admin/survey", tags=["Survey - Admin"])


_CODEBOOK_PATH = Path(__file__).resolve().parents[3] / "data" / "survey_questions.json"
_codebook_cache: Dict[str, Any] | None = None


def _load_codebook() -> Dict[str, Any]:
    global _codebook_cache
    if _codebook_cache is None:
        try:
            _codebook_cache = json.loads(_CODEBOOK_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=make_error(
                    "CODEBOOK_NOT_FOUND",
                    "Survey codebook missing",
                    path=str(_CODEBOOK_PATH),
                ),
            )
    return _codebook_cache


@router.get("/codebook")
async def get_codebook():
    """프론트가 문항/라벨/옵션을 가져갈 단일 진실원."""
    return _load_codebook()


@router.post("/responses", response_model=SurveyResponseRead, status_code=status.HTTP_201_CREATED)
async def upsert_survey_response(
    req: SurveyResponseUpsertRequest,
    db: AsyncSession = Depends(get_db),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
):
    """세션당 1행 idempotent upsert. 종결 상태로 진입하면 잠김."""
    assert_token_matches_session(req.session_uuid, x_session_token)
    session_internal_id = await get_session_internal_id(db, req.session_uuid)
    if session_internal_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error(
                "SESSION_NOT_FOUND",
                "Session not found for survey response",
                session_uuid=req.session_uuid,
            ),
        )

    answers_payload = {
        key: entry.model_dump(exclude_none=True) for key, entry in req.answers.items()
    }

    # snapshot 이 비어 있으면 백엔드가 부팅 시 로드한 코드북을 자동 첨부 (첫 partial 호출에서만 기록됨)
    snapshot = req.survey_snapshot or json.dumps(_load_codebook(), ensure_ascii=False)

    response = await upsert_response(
        db,
        session_id=session_internal_id,
        status=req.status,
        resp_age=req.resp_age,
        resp_gender=req.resp_gender,
        resp_kiosk_freq=req.resp_kiosk_freq,
        answers=answers_payload,
        multi_choices=req.multi_choices,
        free_texts=req.free_texts,
        q7_no_experience=bool(req.q7_no_experience),
        survey_snapshot=snapshot,
        duration_ms=req.duration_ms,
    )
    return serialize_response(response)


@admin_router.get("/responses", response_model=PaginatedResponse[SurveyResponseRead])
async def list_survey_responses(
    req: SurveyListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    items, total = await list_responses(
        db, status=req.status, skip=req.skip, limit=req.limit
    )
    return PaginatedResponse(
        items=[serialize_response(r) for r in items],
        total=total,
        skip=req.skip,
        limit=req.limit,
    )


@admin_router.get("/summary")
async def survey_summary(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    return await get_response_summary(db)
