from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from crud.menu import get_all_menus, get_all_categories, get_menu_detail
from schemas.menu import MenuListRequest, MenuDetailRequest, MenuListResponse, MenuDetailResponse, CategoryResponse

router = APIRouter(prefix="/menus", tags=["Menu"])


@router.get("", response_model=List[MenuListResponse])
async def list_menus(
    req: MenuListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """메뉴 목록. category_id로 필터링 가능."""
    return await get_all_menus(db, category_id=req.category_id)


@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """카테고리 목록."""
    return await get_all_categories(db)


@router.get("/{menu_id}", response_model=MenuDetailResponse)
async def read_menu(
    req: MenuDetailRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """메뉴 상세 + 옵션 그룹/아이템."""
    detail = await get_menu_detail(db, req.menu_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Menu not found")
    return detail
