from typing import List, Optional
from pydantic import BaseModel, Field
from core.enums import ServingTemperature


# ─── Request ───

class MenuListRequest(BaseModel):
    """메뉴 목록 조회 요청"""
    category_name: Optional[str] = Field(None, description="카테고리 이름으로 필터링")
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)
    sort_by: str = Field("name")
    sort_order: str = Field("asc", pattern="^(asc|desc)$")


class CategoryListRequest(BaseModel):
    """카테고리 목록 조회 요청"""
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


class CategoryCreateRequest(BaseModel):
    """카테고리 생성 (관리자)"""
    name: str = Field(..., min_length=1, max_length=50)
    display_order: int = Field(0, ge=0)


class MenuCreateRequest(BaseModel):
    """메뉴 생성 (관리자)"""
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1)
    price: int = Field(..., ge=0)
    icon_emoji: Optional[str] = Field(None, max_length=10)
    calories: Optional[int] = Field(None, ge=0)
    serving_temperature: Optional[ServingTemperature] = None
    is_caffeinated: bool = False
    is_seasonal: bool = False
    sweetness_level: Optional[int] = Field(None, ge=0, le=5)
    bitterness_level: Optional[int] = Field(None, ge=0, le=5)
    description: Optional[str] = Field(None, max_length=255)
    image_url: Optional[str] = Field(None, max_length=500)


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
    category: str
    price: int
    icon_emoji: Optional[str] = None
    calories: Optional[int] = None
    serving_temperature: Optional[str] = None
    is_caffeinated: bool = False
    is_seasonal: bool = False
    sweetness_level: Optional[int] = None
    bitterness_level: Optional[int] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    is_available: bool

    model_config = {"from_attributes": True}


class MenuDetailResponse(MenuListResponse):
    """메뉴 상세 — 옵션 그룹 포함"""
    option_groups: List[OptionGroupResponse]
