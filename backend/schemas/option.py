from typing import List, Optional
from pydantic import BaseModel, Field


# ─── Request ───

class OptionItemUpsertRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    extra_price: int = Field(0, ge=0)
    is_default: bool = False
    is_available: bool = True


class OptionGroupUpsertRequest(BaseModel):
    """옵션 그룹 생성 또는 upsert (관리자)"""
    name: str = Field(..., min_length=1, max_length=50)
    is_required: bool = True
    min_select: int = Field(1, ge=0)
    max_select: int = Field(1, ge=1)
    items: List[OptionItemUpsertRequest] = Field(default_factory=list)


class MenuOptionLinkRequest(BaseModel):
    """메뉴에 옵션 그룹 연결"""
    option_group_name: str = Field(..., min_length=1)
    display_order: int = Field(0, ge=0)


class OptionGroupListRequest(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


# ─── Response ───

class OptionItemResponse(BaseModel):
    id: int
    name: str
    extra_price: int
    is_default: bool
    is_available: bool

    model_config = {"from_attributes": True}


class OptionGroupResponse(BaseModel):
    id: int
    name: str
    is_required: bool
    min_select: int
    max_select: int
    items: List[OptionItemResponse] = []

    model_config = {"from_attributes": True}


class MenuOptionLinkResponse(BaseModel):
    """메뉴-옵션 그룹 연결 응답"""
    menu_id: int
    option_group_id: int
    display_order: int = 0

    model_config = {"from_attributes": True}
