"""공통 응답 스키마"""
from typing import Generic, List, Optional, TypeVar, Any, Dict
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """페이지네이션 응답"""
    items: List[T]
    total: int
    skip: int
    limit: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


def make_error(code: str, message: str, **details) -> Dict[str, Any]:
    """HTTPException(detail=...)용 에러 본문 생성"""
    return ErrorResponse(
        error=ErrorDetail(code=code, message=message, details=details or None)
    ).model_dump()
