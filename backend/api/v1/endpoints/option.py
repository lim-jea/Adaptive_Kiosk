from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from crud.menu import (
    get_menu_by_name,
    get_option_catalog,
    get_option_group_with_items,
    get_option_groups,
    upsert_option_group,
)
from services.voice_prompting import invalidate_menu_catalog_cache
from schemas import (
    OptionCatalogGroup,
    OptionGroupListRequest,
    OptionGroupResponse,
    OptionGroupUpsertRequest,
    PaginatedResponse,
    make_error,
)

router = APIRouter(tags=["Option"])


@router.get("/option-catalog", response_model=list[OptionCatalogGroup])
async def list_option_catalog(
    include_unavailable: bool = Query(
        True, description="숨김 처리된 옵션도 포함해 카탈로그를 보여줄지 여부.",
    ),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """전역 옵션 카탈로그. (group_name, option_name) 단위로 집계해 어떤 메뉴에서
    사용되는지와 대표 메타(필수/min/max)·평균 추가가격을 반환. 관리자 인증 필요."""
    return await get_option_catalog(db, include_unavailable=include_unavailable)


@router.get("/option-groups", response_model=PaginatedResponse[OptionGroupResponse])
async def list_option_groups(
    req: OptionGroupListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    groups, total = await get_option_groups(
        db,
        skip=req.skip,
        limit=req.limit,
        menu_name=req.menu_name,
    )
    return PaginatedResponse(items=groups, total=total, skip=req.skip, limit=req.limit)


@router.get("/option-groups/{group_name}", response_model=OptionGroupResponse)
async def read_option_group(
    group_name: str,
    menu_name: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    detail = await get_option_group_with_items(db, group_name, menu_name=menu_name)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error(
                "OPTION_GROUP_NOT_FOUND",
                "Option group not found",
                group_name=group_name,
                menu_name=menu_name,
            ),
        )
    return detail


@router.post(
    "/option-groups",
    response_model=OptionGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_option_group_endpoint(
    req: OptionGroupUpsertRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    if not req.menu_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=make_error(
                "MENU_NAME_REQUIRED",
                "menu_name is required when writing menu options.",
            ),
        )

    detail = await upsert_option_group(
        db,
        menu_name=req.menu_name,
        name=req.name,
        group_order=req.group_order,
        is_required=req.is_required,
        min_select=req.min_select,
        max_select=req.max_select,
        items=[item.model_dump() for item in req.items],
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("MENU_NOT_FOUND", "Menu not found", menu_name=req.menu_name),
        )
    invalidate_menu_catalog_cache()
    return detail


@router.post(
    "/menus/{menu_name}/option-groups",
    response_model=OptionGroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upsert_menu_option_group(
    menu_name: str,
    req: OptionGroupUpsertRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    menu = await get_menu_by_name(db, menu_name)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("MENU_NOT_FOUND", "Menu not found", menu_name=menu_name),
        )

    detail = await upsert_option_group(
        db,
        menu_name=menu_name,
        name=req.name,
        group_order=req.group_order,
        is_required=req.is_required,
        min_select=req.min_select,
        max_select=req.max_select,
        items=[item.model_dump() for item in req.items],
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=make_error(
                "OPTION_GROUP_UPSERT_FAILED",
                "Failed to write menu option group.",
                menu_name=menu_name,
                group_name=req.name,
            ),
        )
    invalidate_menu_catalog_cache()
    return detail
