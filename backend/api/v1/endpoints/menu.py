from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from crud.menu import (
    get_categories,
    get_menus,
    get_menu_detail,
    create_category,
    create_menu,
)
from schemas.menu import (
    CategoryListRequest,
    CategoryCreateRequest,
    CategoryResponse,
    MenuListRequest,
    MenuCreateRequest,
    MenuListResponse,
    MenuDetailResponse,
)
from schemas.common import PaginatedResponse, make_error

router = APIRouter(tags=["Menu"])


# ─── Categories (별도 리소스) ───

@router.get("/categories", response_model=PaginatedResponse[CategoryResponse])
async def list_categories(
    req: CategoryListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """카테고리 목록."""
    items, total = await get_categories(db, skip=req.skip, limit=req.limit)
    return PaginatedResponse(items=items, total=total, skip=req.skip, limit=req.limit)


@router.post(
    "/categories",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category_endpoint(
    req: CategoryCreateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """카테고리 생성. 관리자 인증 필요."""
    return await create_category(db, name=req.name, display_order=req.display_order)


# ─── Menus ───

@router.get("/menus", response_model=PaginatedResponse[MenuListResponse])
async def list_menus(
    req: MenuListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """메뉴 목록 + 페이지네이션 + 카테고리 필터 + 정렬."""
    items, total = await get_menus(
        db,
        category_name=req.category_name,
        skip=req.skip,
        limit=req.limit,
        sort_by=req.sort_by,
        sort_order=req.sort_order,
    )
    return PaginatedResponse(items=items, total=total, skip=req.skip, limit=req.limit)


@router.post(
    "/menus",
    response_model=MenuListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_menu_endpoint(
    req: MenuCreateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """메뉴 생성. 관리자 인증 필요."""
    data = req.model_dump()
    if data.get("serving_temperature") and hasattr(data["serving_temperature"], "value"):
        data["serving_temperature"] = data["serving_temperature"].value
    return await create_menu(db, data)


@router.get("/menus/{menu_name}", response_model=MenuDetailResponse)
async def read_menu(menu_name: str, db: AsyncSession = Depends(get_db)):
    """메뉴 상세 + 옵션 그룹/아이템."""
    detail = await get_menu_detail(db, menu_name)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("MENU_NOT_FOUND", "Menu not found", menu_name=menu_name),
        )
    return detail
