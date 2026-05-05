from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from crud.menu import (
    create_menu,
    get_categories,
    get_menu_by_id,
    get_menu_detail,
    get_menus,
    replace_menu_option_groups,
    soft_delete_menu,
    soft_delete_option_group,
    update_menu,
)
from schemas import (
    CategoryListRequest,
    CategoryResponse,
    MenuCreateInlineRequest,
    MenuDetailResponse,
    MenuListRequest,
    MenuListResponse,
    MenuUpdateRequest,
    PaginatedResponse,
    make_error,
)

router = APIRouter(tags=["Menu"])


# ─── Categories ─────────────────────────────────────────────────────────────

@router.get("/categories", response_model=PaginatedResponse[CategoryResponse])
async def list_categories(
    req: CategoryListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """카테고리 목록."""
    items, total = await get_categories(db, skip=req.skip, limit=req.limit)
    return PaginatedResponse(items=items, total=total, skip=req.skip, limit=req.limit)


# ─── Menus ──────────────────────────────────────────────────────────────────

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
        include_unavailable=req.include_unavailable,
    )
    return PaginatedResponse(items=items, total=total, skip=req.skip, limit=req.limit)


@router.post(
    "/menus",
    response_model=MenuDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_menu_endpoint(
    req: MenuCreateInlineRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """메뉴 생성. `option_groups`가 함께 오면 옵션도 같이 생성. 관리자 인증 필요."""
    payload = req.model_dump()
    option_groups = payload.pop("option_groups", None)

    temp = payload.get("serving_temperature")
    if temp is not None and hasattr(temp, "value"):
        payload["serving_temperature"] = temp.value

    menu = await create_menu(db, payload)
    if option_groups is not None:
        await replace_menu_option_groups(db, menu=menu, groups=option_groups)

    return await get_menu_detail(db, menu.name, include_unavailable_options=True)


@router.patch("/menus/{menu_id}", response_model=MenuDetailResponse)
async def update_menu_endpoint(
    menu_id: int,
    req: MenuUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """메뉴 부분 수정. `option_groups`가 함께 오면 해당 그룹들을 통째로 교체."""
    data = req.model_dump(exclude_unset=True)
    option_groups = data.pop("option_groups", None)

    temp = data.get("serving_temperature")
    if temp is not None and hasattr(temp, "value"):
        data["serving_temperature"] = temp.value

    menu = await update_menu(db, menu_id, data) if data else await get_menu_by_id(db, menu_id)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("MENU_NOT_FOUND", "Menu not found", menu_id=menu_id),
        )

    if option_groups is not None:
        await replace_menu_option_groups(db, menu=menu, groups=option_groups)

    return await get_menu_detail(db, menu.name, include_unavailable_options=True)


@router.delete("/menus/{menu_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_endpoint(
    menu_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """메뉴 소프트 삭제 (`is_available=false`). 주문 이력 무결성을 위해 row는 유지."""
    menu = await soft_delete_menu(db, menu_id)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("MENU_NOT_FOUND", "Menu not found", menu_id=menu_id),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/menus/{menu_id}/option-groups/{group_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_menu_option_group(
    menu_id: int,
    group_name: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """옵션 그룹 소프트 삭제 (그룹 내 모든 옵션 `is_available=false`)."""
    affected = await soft_delete_option_group(db, menu_id=menu_id, group_name=group_name)
    if affected == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error(
                "OPTION_GROUP_NOT_FOUND",
                "Option group not found",
                menu_id=menu_id, group_name=group_name,
            ),
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/menus/{menu_name}", response_model=MenuDetailResponse)
async def read_menu(
    menu_name: str,
    include_unavailable_options: bool = Query(
        False, description="관리자용. 숨김 처리된 옵션까지 함께 반환.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """메뉴 상세 + 옵션 그룹/아이템. 관리자 페이지는 ?include_unavailable_options=true."""
    detail = await get_menu_detail(
        db, menu_name, include_unavailable_options=include_unavailable_options
    )
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("MENU_NOT_FOUND", "Menu not found", menu_name=menu_name),
        )
    return detail
