from typing import List, Optional
from pydantic import BaseModel, Field


# ─── Request ───

class MenuListRequest(BaseModel):
    """메뉴 목록 조회 요청"""
    category_name: Optional[str] = Field(None, description="카테고리 이름으로 필터링")


class MenuDetailRequest(BaseModel):
    """메뉴 상세 조회 요청"""
    menu_name: str = Field(..., description="메뉴 이름으로 조회")


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
    items: List[OptionItemResponse]

    model_config = {"from_attributes": True}


class CategoryResponse(BaseModel):
    id: int
    name: str
    display_order: int = 0

    model_config = {"from_attributes": True}


class MenuListResponse(BaseModel):
    id: int
    name: str
    category_id: int
    category_name: str = ""
    price: int
    emoji: Optional[str] = None
    cal: Optional[int] = None
    temp: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool

    model_config = {"from_attributes": True}


class MenuDetailResponse(BaseModel):
    id: int
    name: str
    category_id: int
    category_name: str = ""
    price: int
    emoji: Optional[str] = None
    cal: Optional[int] = None
    temp: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool
    option_groups: List[OptionGroupResponse]

    model_config = {"from_attributes": True}
