from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import verify_credentials
from crud.menu import (
    get_option_groups,
    get_option_group_with_items,
    upsert_option_group,
    get_menu_by_name,
    get_option_group_by_name,
    link_menu_option_group,
)
from schemas.option import (
    OptionGroupListRequest,
    OptionGroupUpsertRequest,
    OptionGroupResponse,
    MenuOptionLinkRequest,
    MenuOptionLinkResponse,
)
from schemas.common import PaginatedResponse, make_error

router = APIRouter(tags=["Option"])


# ─── Option Group ───

@router.get("/option-groups", response_model=PaginatedResponse[OptionGroupResponse])
async def list_option_groups(
    req: OptionGroupListRequest = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """옵션 그룹 목록 (각 그룹 내 아이템 포함)."""
    groups, total = await get_option_groups(db, skip=req.skip, limit=req.limit)
    items = []
    for og in groups:
        detail = await get_option_group_with_items(db, og.name)
        if detail:
            items.append(detail)
    return PaginatedResponse(items=items, total=total, skip=req.skip, limit=req.limit)


@router.get("/option-groups/{group_name}", response_model=OptionGroupResponse)
async def read_option_group(group_name: str, db: AsyncSession = Depends(get_db)):
    """옵션 그룹 단건 조회 + 아이템 포함."""
    detail = await get_option_group_with_items(db, group_name)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("OPTION_GROUP_NOT_FOUND", "Option group not found", group_name=group_name),
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
    """옵션 그룹 생성 또는 업데이트 (upsert). 아이템도 함께 upsert. 관리자 인증 필요."""
    items_data = [item.model_dump() for item in req.items]
    og = await upsert_option_group(
        db,
        name=req.name,
        is_required=req.is_required,
        min_select=req.min_select,
        max_select=req.max_select,
        items=items_data,
    )
    detail = await get_option_group_with_items(db, og.name)
    return detail


# ─── Menu ↔ Option Group 연결 ───

@router.post(
    "/menus/{menu_name}/option-groups",
    response_model=MenuOptionLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_menu_to_option_group(
    menu_name: str,
    req: MenuOptionLinkRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_credentials),
):
    """메뉴에 옵션 그룹 연결. 관리자 인증 필요."""
    menu = await get_menu_by_name(db, menu_name)
    if not menu:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error("MENU_NOT_FOUND", "Menu not found", menu_name=menu_name),
        )
    og = await get_option_group_by_name(db, req.option_group_name)
    if not og:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=make_error(
                "OPTION_GROUP_NOT_FOUND",
                "Option group not found",
                option_group_name=req.option_group_name,
            ),
        )
    link = await link_menu_option_group(
        db, menu_id=menu.id, option_group_id=og.id, display_order=req.display_order
    )
    return link
