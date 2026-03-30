from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.menu import get_all_menus, get_all_categories
from schemas.analytics import MenuResponse, CategoryResponse

router = APIRouter(prefix="/menus", tags=["Menu"])


@router.get("", response_model=List[MenuResponse])
async def list_menus(category: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """전체 메뉴 목록을 조회합니다. category 파라미터로 필터링 가능."""
    return await get_all_menus(db, category_id=category)


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """전체 카테고리 목록을 조회합니다."""
    return await get_all_categories(db)
