// 키오스크 메인 페이지 — 메뉴 동적 로드 + 옵션 모달 + 장바구니
// 메뉴/카테고리/옵션은 모두 백엔드 API에서 동적으로 가져옴

import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api.js'
import { useSession } from '../store/sessionStore.jsx'
import { useVoiceOrder } from '../hooks/useVoiceOrder.js'
import { useLogger } from '../hooks/useLogger.js'
import VoiceOverlay from '../components/VoiceOverlay.jsx'
import RecommendationPanel from '../components/RecommendationPanel.jsx'
import { shouldShowRecommendation } from '../utils/recommendation'

// 중장년 선호 메뉴 순서
const MIDDLE_PREFERRED = [
  '아메리카노', '카페라떼', '드립 커피', '콜드브루',
  '디카페인', '저당', '아몬드 라떼', '오트 라떼',
  '녹차 라떼', '카푸치노',
]

function normalizeOptionIds(optionIds = []) {
  return [...optionIds].map(Number).filter(Boolean).sort((a, b) => a - b)
}

function getCartOptionIds(item) {
  return normalizeOptionIds((item.selectedOptions || []).map((option) => option.option_item_id))
}

function sameOptionSelection(item, optionItemIds = []) {
  const left = getCartOptionIds(item)
  const right = normalizeOptionIds(optionItemIds)
  if (left.length !== right.length) return false
  return left.every((value, index) => value === right[index])
}

function getOptionDisplayName(name) {
  const sizeNames = {
    Tall: '소형 355ml',
    Grande: '기본 473ml',
    Venti: '대형 591ml',
  }
  return sizeNames[name] || name
}

export default function MiddleKioskPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const [categories, setCategories] = useState([])
  const [menus, setMenus] = useState([])
  const [activeCategory, setActiveCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [optionMenu, setOptionMenu] = useState(null)
  const [optionPreview, setOptionPreview] = useState([])  // 음성으로 미리 선택된 옵션 ID
  const [cartOpen, setCartOpen] = useState(true)
  const [voiceFlash, setVoiceFlash] = useState(null)      // 'category:커피' 등 잠깐 하이라이트
  const flashTimerRef = useRef(null)
  const cartLoadedRef = useRef(false)
  const lastSyncedCartRef = useRef('')

  const serializeCartForSync = useCallback((cart) => JSON.stringify(
    cart.map((item) => ({
      menu_name: item.menuName,
      quantity: item.quantity,
      from_recommendation: Boolean(item.fromRecommendation),
      selected_options: item.selectedOptions || [],
    }))
  ), [])

  const mapServerCartToLocal = useCallback((items = []) => items.map((item) => {
    const optionLabels = (item.options || []).map((option) => option.option_name)
    const selectedOptions = (item.options || []).map((option) => ({
      option_item_id: option.option_item_id,
    }))
    const optionExtra = (item.options || []).reduce((sum, option) => sum + option.extra_price, 0)
    const menuMeta = menus.find((m) => m.name === item.menu_name) || null

    return {
      cartItemId: item.line_id,
      menuId: item.menu_id,
      menuName: item.menu_name,
      displayName: item.menu_name,
      basePrice: item.unit_price - optionExtra,
      unitPrice: item.unit_price,
      quantity: item.quantity,
      fromRecommendation: Boolean(item.from_recommendation),
      selectedOptions,
      optionLabels,
      menuImageUrl: menuMeta?.image_url || null,
      menuEmoji: menuMeta?.icon_emoji || '☕',
    }
  }), [menus])

  const flash = useCallback((key) => {
    setVoiceFlash(key)
    if (flashTimerRef.current) clearTimeout(flashTimerRef.current)
    flashTimerRef.current = setTimeout(() => setVoiceFlash(null), 1200)
  }, [])

  // 마운트 시 카테고리 + 메뉴 동시 로드
  useEffect(() => {
    const loadAll = async () => {
      const startedAt = performance.now()
      try {
        const [catRes, menuRes] = await Promise.all([
          api.get('/api/v1/categories', { params: { limit: 1000 } }),
          api.get('/api/v1/menus', { params: { limit: 1000 } }),
        ])
        setCategories(catRes.data.items || [])
        setMenus(menuRes.data.items || [])
        logClientTiming('kiosk.loadMenusAndCategories', performance.now() - startedAt, {
          category_count: (catRes.data.items || []).length,
          menu_count: (menuRes.data.items || []).length,
        })
      } catch (err) {
        logClientTiming('kiosk.loadMenusAndCategories.error', performance.now() - startedAt)
        console.error('메뉴 로드 실패:', err)
      } finally {
        setLoading(false)
      }
    }
    loadAll()
  }, [])

  // 옵션 편집 진입 (CartReview 또는 카트 패널)
  const editTriggeredRef = useRef(null)
  useEffect(() => {
    if (!state.editCartItemId) {
      editTriggeredRef.current = null
      return
    }
    if (editTriggeredRef.current === state.editCartItemId) return
    editTriggeredRef.current = state.editCartItemId
    const cartItem = state.cart.find((item) => item.cartItemId === state.editCartItemId)
    if (!cartItem) {
      dispatch({ type: ACTIONS.SET_EDIT_TARGET, payload: { cartItemId: null } })
      return
    }
    const editSource = state.editCartSource
    ;(async () => {
      try {
        const detailRes = await api.get(`/api/v1/menus/${encodeURIComponent(cartItem.menuName)}`)
        setOptionMenu({
          ...detailRes.data,
          editingItemId: cartItem.cartItemId,
          editSource,
          initialSelections: (cartItem.selectedOptions || []).map((o) => o.option_item_id),
          initialQuantity: cartItem.quantity,
          fromRecommendation: Boolean(cartItem.fromRecommendation),
        })
      } catch (err) {
        console.error('옵션 편집용 메뉴 로드 실패:', err)
        dispatch({ type: ACTIONS.SET_EDIT_TARGET, payload: { cartItemId: null } })
      }
    })()
  }, [state.editCartItemId, state.editCartSource, state.cart, dispatch, ACTIONS])

  useEffect(() => {
    const enteredAt = Date.now()
    if (state.sessionUuid) {
      logger.logScreenEnter('kiosk', {
        is_simple_mode: state.isSimpleMode,
      })
    }
    return () => {
      if (state.sessionUuid) logger.logScreenExit('kiosk', Date.now() - enteredAt)
    }
  }, [logger, state.isSimpleMode, state.sessionUuid])

  useEffect(() => {
    const loadServerCart = async () => {
      if (!state.sessionUuid) {
        cartLoadedRef.current = false
        lastSyncedCartRef.current = ''
        return
      }

      const startedAt = performance.now()
      try {
        const { data } = await api.get(`/api/v1/carts/${state.sessionUuid}`)
        const localCart = mapServerCartToLocal(data.items || [])
        lastSyncedCartRef.current = serializeCartForSync(localCart)
        dispatch({
          type: ACTIONS.REPLACE_CART,
          payload: { cart: localCart },
        })
        logClientTiming('kiosk.loadServerCart', performance.now() - startedAt, {
          item_count: localCart.length,
        })
      } catch (err) {
        logClientTiming('kiosk.loadServerCart.error', performance.now() - startedAt)
        console.error('서버 장바구니 로드 실패:', err)
      } finally {
        cartLoadedRef.current = true
      }
    }

    loadServerCart()
  }, [state.sessionUuid, dispatch, ACTIONS, mapServerCartToLocal, serializeCartForSync])

  useEffect(() => {
    const syncCartToServer = async () => {
      if (!state.sessionUuid || !cartLoadedRef.current) return

      const signature = serializeCartForSync(state.cart)
      if (signature === lastSyncedCartRef.current) return

      const startedAt = performance.now()
      try {
        await api.put(`/api/v1/carts/${state.sessionUuid}`, {
          items: state.cart.map((item) => ({
            menu_name: item.menuName,
            quantity: item.quantity,
            from_recommendation: Boolean(item.fromRecommendation),
            selected_options: item.selectedOptions || [],
          })),
        })
        lastSyncedCartRef.current = signature
        logClientTiming('kiosk.syncCartToServer', performance.now() - startedAt, {
          item_count: state.cart.length,
        })
      } catch (err) {
        logClientTiming('kiosk.syncCartToServer.error', performance.now() - startedAt, {
          item_count: state.cart.length,
        })
        console.error('서버 장바구니 동기화 실패:', err)
      }
    }

    syncCartToServer()
  }, [state.sessionUuid, state.cart, serializeCartForSync])

  // 중장년 선호 메뉴 앞으로 정렬
  const filteredMenus = useMemo(() => {
    const list = activeCategory === 'all'
      ? menus
      : menus.filter((m) => m.category === activeCategory)
  
    return [...list].sort((a, b) => {
      const aIdx = MIDDLE_PREFERRED.findIndex((name) => a.name.includes(name))
      const bIdx = MIDDLE_PREFERRED.findIndex((name) => b.name.includes(name))
      if (aIdx === -1 && bIdx === -1) return 0
      if (aIdx === -1) return 1
      if (bIdx === -1) return -1
      return aIdx - bIdx
    })
  }, [menus, activeCategory])

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)

  const handleCategoryChange = useCallback((categoryName) => {
    logger.log('navigation', 'kiosk', {
      actionName: 'category_tab_click',
      targetType: 'category',
      targetLabel: categoryName,
    })
    setActiveCategory(categoryName)
  }, [logger])

  // 메뉴 클릭 → 상세 (옵션 그룹 포함) 조회 후 모달 오픈
  const handleMenuClick = useCallback(async (menu, meta = {}) => {
    logger.log(meta.fromRecommendation ? 'recommendation' : 'click', 'kiosk', {
      actionName: meta.fromRecommendation ? 'recommendation_click' : 'menu_click',
      targetType: 'menu',
      targetId: menu.id,
      targetLabel: menu.name,
      source: meta.fromRecommendation ? 'recommendation' : 'ui',
    })
    const startedAt = performance.now()
    try {
      const detailRes = await api.get(`/api/v1/menus/${encodeURIComponent(menu.name)}`)
      setOptionMenu({
        ...detailRes.data,
        fromRecommendation: Boolean(meta.fromRecommendation),
      })
      logClientTiming('kiosk.loadMenuDetail', performance.now() - startedAt, {
        menu_name: menu.name,
      })
    } catch (err) {
      logClientTiming('kiosk.loadMenuDetail.error', performance.now() - startedAt, {
        menu_name: menu.name,
      })
      console.error('메뉴 상세 로드 실패:', err)
    }
  }, [logger])

  const handleConfirmOption = useCallback(({ selectedOptionIds, optionLabels, quantity, unitPrice }) => {
    const cartItemId = `${optionMenu.name}_${[...selectedOptionIds].sort().join('-')}`
    const isEditing = Boolean(optionMenu.editingItemId)
    const newItem = {
      cartItemId,
      menuId: optionMenu.id,
      menuName: optionMenu.name,
      displayName: optionMenu.name,
      basePrice: optionMenu.price,
      unitPrice,
      quantity,
      fromRecommendation: Boolean(optionMenu.fromRecommendation),
      selectedOptions: selectedOptionIds.map((id) => ({ option_item_id: id })),
      optionLabels,
      menuImageUrl: optionMenu.image_url || null,
      menuEmoji: optionMenu.icon_emoji || '☕',
    }

    logger.log('cart', 'kiosk', {
      actionName: isEditing ? 'cart_edit_commit' : 'cart_add',
      targetType: 'menu',
      targetId: optionMenu.id,
      targetLabel: optionMenu.name,
      source: optionMenu.fromRecommendation ? 'recommendation' : 'ui',
      payload: {
        quantity,
        option_item_ids: selectedOptionIds,
        option_labels: optionLabels,
        from_recommendation: Boolean(optionMenu.fromRecommendation),
        old_cart_item_id: isEditing ? optionMenu.editingItemId : undefined,
      },
    })
    if (isEditing) {
      dispatch({
        type: ACTIONS.REPLACE_CART_ITEM,
        payload: {
          oldCartItemId: optionMenu.editingItemId,
          oldMatch: {
            menuName: optionMenu.name,
            optionItemIds: optionMenu.initialSelections || [],
          },
          newItem,
        },
      })
      setOptionMenu(null)
      if (optionMenu.editSource !== 'cart_panel') {
        navigate('/cart-review')
      }
      return
    }
    dispatch({ type: ACTIONS.ADD_TO_CART, payload: newItem })
    setCartOpen(true)
    setOptionMenu(null)
  }, [optionMenu, logger, dispatch, ACTIONS, navigate])

  const handleEditCartFromPanel = useCallback((item) => {
    logger.log('cart', 'kiosk', {
      actionName: 'cart_edit_open',
      targetType: 'cart_item',
      targetId: item.cartItemId,
      targetLabel: item.menuName,
      payload: { source: 'cart_panel', menu_name: item.menuName, option_item_ids: (item.selectedOptions || []).map((o) => o.option_item_id) },
    })
    dispatch({
      type: ACTIONS.SET_EDIT_TARGET,
      payload: { cartItemId: item.cartItemId, source: 'cart_panel' },
    })
  }, [logger, dispatch, ACTIONS])

  const handleQtyChange = useCallback((cartItemId, delta) => {
    const item = state.cart.find((i) => i.cartItemId === cartItemId)
    if (!item) return
    logger.log('cart', 'kiosk', {
      actionName: 'cart_qty_change',
      targetType: 'cart_item',
      targetId: cartItemId,
      targetLabel: item.menuName,
      payload: {
        previous_quantity: item.quantity,
        next_quantity: item.quantity + delta,
      },
    })
    dispatch({
      type: ACTIONS.UPDATE_CART_QTY,
      payload: { cartItemId, quantity: item.quantity + delta },
    })
  }, [state.cart, logger, dispatch, ACTIONS])

  const handleOrder = useCallback(() => {
    if (state.cart.length === 0 || !state.sessionUuid) return
    logger.log('navigation', 'kiosk', {
      actionName: 'go_to_cart_review',
      targetType: 'button',
      targetLabel: 'cart_review',
      payload: { total_price: totalPrice, total_count: totalCount },
    })
    navigate('/cart-review')
  }, [logger, navigate, state.cart.length, state.sessionUuid, totalCount, totalPrice])

  const handleBack = useCallback(() => {
    logger.log('navigation', 'kiosk', {
      actionName: 'back_home',
      targetType: 'button',
      targetLabel: 'home',
    })
    navigate('/')
  }, [logger, navigate])

  // ─── 음성 주문 통합 ─────────────────────────────────────────────────
  // 액션 핸들러는 비동기 fetch 도중 cart가 바뀌어도 항상 최신 cart를 보도록 ref 사용
  const cartRef = useRef(state.cart)
  useEffect(() => { cartRef.current = state.cart }, [state.cart])

  const handleVoiceAction = useCallback(async (action) => {
    logger.log('voice', 'kiosk', {
      actionName: 'voice_action_applied',
      source: 'voice',
      payload: { type: action.type },
    })
    switch (action.type) {
      case 'navigate': {
        // 옵션 모달이 열린 상태에서 다른 화면(카테고리/결제/카트 등)으로 이동하면
        // 모달이 남아 UX가 깨지므로, menu_detail을 여는 경우를 제외하고는 항상 닫는다.
        if (action.target !== 'menu_detail') {
          setOptionMenu(null)
          setOptionPreview([])
        }
        if (action.target === 'category' && action.category_name) {
          setActiveCategory(action.category_name)
          flash(`category:${action.category_name}`)
        } else if (action.target === 'menu_list') {
          setActiveCategory('all')
          flash('category:all')
        } else if (action.target === 'menu_detail' && action.menu_name) {
          flash(`menu:${action.menu_name}`)
          setOptionPreview([])  // 이전 메뉴의 preview 잔여 제거
          try {
            const detail = await api.get(`/api/v1/menus/${encodeURIComponent(action.menu_name)}`)
            setOptionMenu(detail.data)
          } catch (e) { console.error(e) }
        } else if (action.target === 'cart') {
          logger.log('navigation', 'kiosk', {
            actionName: 'cart_open',
            source: 'voice',
            targetType: 'panel',
            targetLabel: 'cart',
          })
          setCartOpen(true)
        } else if (action.target === 'middlepayment' || action.target === 'payment') {
          // 음성으로 결제 이동 — 카트 비어 있으면 이동 안 함
          if (cartRef.current.length > 0) navigate('/cart-review')
          else console.warn('[voice] cart empty, payment navigation skipped')
        }
        break
      }
      case 'option_preview': {
        // 옵션 모달이 안 떠 있으면 먼저 띄우고 미리 선택만 표시
        if (!optionMenu || optionMenu.name !== action.menu_name) {
          try {
            const detail = await api.get(`/api/v1/menus/${encodeURIComponent(action.menu_name)}`)
            setOptionMenu(detail.data)
          } catch (e) { console.error(e) }
        }
        setOptionPreview(action.option_item_ids || [])
        logger.log('option', 'kiosk', {
          actionName: 'option_preview',
          source: 'voice',
          targetType: 'menu',
          targetLabel: action.menu_name,
          payload: { option_item_ids: action.option_item_ids || [] },
        })
        flash(`option:${action.menu_name}`)
        break
      }
      case 'cart_add': {
        try {
          const detail = await api.get(`/api/v1/menus/${encodeURIComponent(action.menu_name)}`)
          const menu = detail.data
          const optionItems = []
          const optionLabels = []
          let extra = 0
          for (const g of menu.option_groups || []) {
            for (const it of g.items || []) {
              if (action.option_item_ids?.includes(it.id)) {
                optionItems.push({ option_item_id: it.id })
                optionLabels.push(getOptionDisplayName(it.name))
                extra += it.extra_price
              }
            }
          }
          const cartItemId = `${menu.name}_${[...(action.option_item_ids || [])].sort().join('-')}`
          dispatch({
            type: ACTIONS.ADD_TO_CART,
            payload: {
              cartItemId,
              menuId: menu.id,
              menuName: menu.name,
              displayName: menu.name,
              basePrice: menu.price,
              unitPrice: menu.price + extra,
              quantity: action.quantity || 1,
              fromRecommendation: false,
              selectedOptions: optionItems,
              optionLabels,
            },
          })
          setOptionMenu(null)   // 음성으로 옵션 확정 시 모달 닫기
          setOptionPreview([])
        } catch (e) { console.error(e) }
        break
      }
      case 'cart_remove': {
        let item = null
        if (action.cart_line_id) {
          item = cartRef.current.find((i) => i.cartItemId === action.cart_line_id) || null
        }
        if (!item && action.option_item_ids?.length) {
          const candidates = cartRef.current.filter(
            (i) => i.menuName === action.menu_name && sameOptionSelection(i, action.option_item_ids)
          )
          item = candidates[candidates.length - 1] || null
        }
        if (!item) {
          const candidates = cartRef.current.filter((i) => i.menuName === action.menu_name)
          item = candidates[candidates.length - 1] || null
        }
        if (item) dispatch({ type: ACTIONS.REMOVE_FROM_CART, payload: { cartItemId: item.cartItemId } })
        if (item) {
          logger.log('cart', 'kiosk', {
            actionName: 'cart_remove',
            source: 'voice',
            targetType: 'cart_item',
            targetId: item.cartItemId,
            targetLabel: item.menuName,
          })
        }
        break
      }
      case 'cart_update': {
        let item = null
        if (action.cart_line_id) {
          item = cartRef.current.find((i) => i.cartItemId === action.cart_line_id) || null
        }
        if (!item && action.option_item_ids?.length) {
          item = cartRef.current.find(
            (i) => i.menuName === action.menu_name && sameOptionSelection(i, action.option_item_ids)
          ) || null
        }
        if (!item) {
          item = cartRef.current.find((i) => i.menuName === action.menu_name) || null
        }
        if (item) dispatch({
          type: ACTIONS.UPDATE_CART_QTY,
          payload: { cartItemId: item.cartItemId, quantity: action.quantity },
        })
        if (item) {
          logger.log('cart', 'kiosk', {
            actionName: 'cart_qty_change',
            source: 'voice',
            targetType: 'cart_item',
            targetId: item.cartItemId,
            targetLabel: item.menuName,
            payload: { next_quantity: action.quantity },
          })
        }
        break
      }
      case 'place_order': {
        setOptionMenu(null)
        setOptionPreview([])
        if (cartRef.current.length > 0) navigate('/cart-review')
        break
      }
      case 'scroll': {
        window.scrollBy({ top: action.direction === 'down' ? 300 : -300, behavior: 'smooth' })
        break
      }
      default: break
    }
  }, [dispatch, ACTIONS, logger, navigate])

  const voice = useVoiceOrder({
    sessionUuid: state.sessionUuid,
    selectedCategory: activeCategory === 'all' ? null : activeCategory,
    selectedMenuName: optionMenu?.name || null,
    onAction: handleVoiceAction,
    onVoiceEvent: (eventName, payload = {}) => {
      logger.log('voice', 'kiosk', {
        actionName: eventName,
        source: 'voice',
        payload,
      })
    },
    autoStart: state.isSimpleMode,
    ttsRate: state.isSimpleMode ? 0.65 : 0.85,
  })

  const hasUserProfile = state.gender && (state.ageGroup || state.ageEst)
  // 미성년 등으로 추천 패널이 null 반환 시 wrapper 도 숨겨 오른쪽 빈 공간 방지.
  const showSidebar = shouldShowRecommendation({
    ageGroup: state.ageGroup,
    ageEst: state.ageEst,
    isChild: false,
    hasUserProfile,
  })

  const handleRecommendSelect = (menuName, meta = {}) => {
    if (activeCategory !== 'all') setActiveCategory('all')
    const menu = menus.find((m) => m.name === menuName)
    if (menu) handleMenuClick(menu, { fromRecommendation: true, ...meta })
  }

  const handleCallStaff = useCallback(() => {
    logger.log('click', 'kiosk', {
      actionName: 'call_staff',
      targetType: 'button',
      targetLabel: 'call_staff',
    })
  }, [logger])

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 헤더 */}
      <header className="px-4 py-3 flex items-center justify-between sticky top-0 z-10 shadow-sm"
        style={{ background: '#f4a261' }}>
        <button onClick={handleBack} className="text-amber-400 hover:text-amber-200 p-2 -ml-2 text-sm font-medium">
          ← 뒤로
        </button>
        <div className="flex items-center gap-2">
          <span className="text-lg">☕</span>
          <h1 className="text-base font-black text-white tracking-widest">BREW AI</h1>
        </div>
        <div className="w-10" />
      </header>

      {/* 카테고리 탭 (동적) */}
      <div className="border-b flex overflow-x-auto sticky top-[56px] z-10"
        style={{ background: '#fff8f3' }}>
        <MiddleCategoryTab
          label="전체"
          active={activeCategory === 'all'}
          flashing={voiceFlash === 'category:all'}
          onClick={() => handleCategoryChange('all')}
        />
        {categories.map((cat) => (
          <MiddleCategoryTab
            key={cat.id}
            label={cat.name}
            active={activeCategory === cat.name}
            flashing={voiceFlash === `category:${cat.name}`}
            onClick={() => handleCategoryChange(cat.name)}
          />
        ))}
      </div>

      {/* 메뉴 그리드 + 추천 패널 */}
      <div className={`flex-1 flex flex-col ${showSidebar ? 'lg:flex-row' : ''}`}>
        {/* 왼쪽 — 메뉴 영역 */}
        <div className="order-2 flex-1 p-4 pt-20 pb-40 lg:order-1">
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <div className="w-8 h-8 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : (
            <>
              {/* 메뉴 목록 */}
              {filteredMenus.length === 0 ? (
                <p className="text-center mt-12" style={{ color: '#f4a261' }}>해당 카테고리 메뉴가 없습니다</p>
              ) : (
                <div className={`grid ${showSidebar ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-3' : 'grid-cols-2 md:grid-cols-3 lg:grid-cols-4'} gap-3`}>
                  {filteredMenus.map((menu) => (
                    <MiddleMenuCard
                      key={menu.id}
                      menu={menu}
                      cartCount={state.cart
                        .filter((i) => i.menuName === menu.name)
                        .reduce((s, i) => s + i.quantity, 0)}
                      onClick={() => handleMenuClick(menu)}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* 우측 세로 추천 패널 */}
        {showSidebar && (
          <div className="order-1 w-full flex-shrink-0 border-b lg:order-2 lg:w-72 lg:border-b-0 lg:border-l" style={{ borderColor: '#fde8d8', background: '#fff8f3' }}>
            <div className="p-3 lg:sticky lg:top-[104px] lg:max-h-[calc(100vh-104px-80px)] lg:overflow-y-auto">
              {!loading && (
                <RecommendationPanel
                  gender={state.gender}
                  age={state.ageEst}
                  ageGroup={state.ageGroup}
                  menus={menus}
                  cartItems={state.cart}
                  onSelectMenu={handleRecommendSelect}
                  vertical={true}
                />
              )}
            </div>
          </div>
        )}
      </div>

      {/* 하단 장바구니 바 */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg z-20">
        {cartOpen && state.cart.length > 0 && (
          <div className="max-h-[190px] overflow-y-auto border-b divide-y bg-gray-50">
            {state.cart.map((item) => (
              <MiddleCartRow
                key={item.cartItemId}
                item={item}
                onQtyChange={(delta) => handleQtyChange(item.cartItemId, delta)}
                onEditOptions={handleEditCartFromPanel}
              />
            ))}
            <div className="px-4 py-2 flex justify-between text-sm font-bold text-gray-700 bg-white">
              <span>합계</span>
              <span className="text-amber-600">{totalPrice.toLocaleString()}원</span>
            </div>
          </div>
        )}

        <div className="px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setCartOpen((v) => !v)}
            disabled={state.cart.length === 0}
            className={`relative flex items-center justify-center w-12 h-12 rounded-2xl border-2 transition-colors flex-shrink-0
            style={{
              borderColor: state.cart.length > 0 ? '#f4a261' : '#e5e7eb',
              color: state.cart.length > 0 ? '#f4a261' : '#d1d5db',
            }}
              ${state.cart.length > 0
                ? 'border-amber-400 text-amber-600 hover:bg-amber-50'
                : 'border-gray-200 text-gray-300 cursor-not-allowed'}`}
          >
            <span className="text-xl">🛒</span>
            {totalCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full text-white text-xs font-bold flex items-center justify-center"
                style={{ background: '#f4a261' }}>
                {totalCount > 9 ? '9+' : totalCount}
              </span>
            )}
          </button>

          <button
            onClick={handleOrder}
            disabled={state.cart.length === 0}
            className={`flex-1 min-h-[48px] py-3 rounded-2xl text-base font-bold transition-colors
            style={{
              background: state.cart.length > 0 ? '#f4a261' : '#e5e7eb',
              color: state.cart.length > 0 ? '#fff' : '#9ca3af',
            }}
              ${state.cart.length > 0
                ? 'bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
          >
            {state.cart.length === 0
              ? '메뉴를 선택해주세요'
              : `결제하기 · ${totalPrice.toLocaleString()}원`}
          </button>
        </div>
      </div>

      {/* 음성 주문 오버레이 */}
      <VoiceOverlay voice={voice} isSimpleMode={state.isSimpleMode} onCallStaff={handleCallStaff} />

      {/* 옵션 선택 모달 */}
      {optionMenu && (
        <MiddleOptionModal
          menu={optionMenu}
          previewSelections={optionMenu.initialSelections?.length ? optionMenu.initialSelections : optionPreview}
          initialQuantity={optionMenu.initialQuantity || 1}
          editing={Boolean(optionMenu.editingItemId)}
          onClose={() => {
            if (optionMenu.editingItemId) {
              dispatch({ type: ACTIONS.SET_EDIT_TARGET, payload: { cartItemId: null } })
            }
            setOptionMenu(null)
            setOptionPreview([])
          }}
          onConfirm={handleConfirmOption}
          onLog={(event) => logger.log(event.eventType, 'kiosk', event)}
        />
      )}
    </div>
  )
}

/** 카테고리 탭 — 활성 시 자동 스크롤 + 음성 하이라이트 잠깐 깜빡 */
function MiddleCategoryTab({ label, active, flashing, onClick }) {
  const ref = useRef(null)
  useEffect(() => {
    if (active && ref.current) {
      ref.current.scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' })
    }
  }, [active])
  return (
    <button
      ref={ref}
      onClick={onClick}
      className={`flex-shrink-0 px-5 py-3 text-sm font-medium border-b-2 transition-all
        ${active
          ? 'border-amber-500 text-amber-700'
          : 'border-transparent text-gray-500 hover:text-gray-700'}
        ${flashing ? 'bg-amber-100 scale-105' : ''}`}
      style={{
        borderBottomColor: active ? '#f4a261' : 'transparent',
        color: active ? '#c2703a' : '#6b7280',
      }}
    >
      {label}
    </button>
  )
}

/** 메뉴 카드 */
function MiddleMenuCard({ menu, cartCount, onClick }) {
  return (
    <button
      onClick={onClick}
      className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden text-left active:scale-95 transition-all duration-150 w-full hover:shadow-md hover:border-amber-200"
      style={{ background: '#fff', border: '1px solid #fde8d8' }}
    >
      <div className="relative overflow-hidden" style={{ paddingBottom: '75%' }}>
        <div className="absolute inset-0">
          {menu.image_url
            ? <img
                src={menu.image_url}
                alt={menu.name}
                className="h-full w-full object-cover"
                onError={(e) => {
                  e.target.style.display = 'none'
                  e.target.nextSibling.style.display = 'flex'
                }}
              />
            : null}
          <div
            className="h-full w-full bg-amber-50 items-center justify-center text-5xl"
            style={{ display: menu.image_url ? 'none' : 'flex' }}
          >
            {menu.icon_emoji || '🍽️'}
          </div>
        </div>
        {cartCount > 0 && (
          <span className="absolute top-2 right-2 w-6 h-6 rounded-full bg-amber-500 text-white text-xs font-bold flex items-center justify-center shadow-lg z-10">
            {cartCount}
          </span>
        )}
      </div>
      <div className="p-3">
        <p className="font-semibold text-gray-800 text-sm leading-tight mb-1 line-clamp-2">{menu.name}</p>
        <p className="text-amber-600 font-bold text-sm">{menu.price.toLocaleString()}원~</p>
      </div>
    </button>
  )
}

/** 장바구니 행 */
function MiddleCartRow({ item, onQtyChange, onEditOptions }) {
  const optionLabel = (item.optionLabels || []).join(' · ')
  return (
    <div className="flex items-center px-4 py-2.5 gap-2 bg-white">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{item.displayName}</p>
        {optionLabel && <p className="text-xs text-gray-400">{optionLabel}</p>}
      </div>
      {onEditOptions && (
        <button
          onClick={() => onEditOptions(item)}
          className="flex-shrink-0 px-2 h-7 rounded-full border border-amber-300 text-amber-600 text-xs font-bold hover:bg-amber-50"
        >
          옵션
        </button>
      )}
      <div className="flex items-center gap-1.5 flex-shrink-0">
        <button
          onClick={() => onQtyChange(-1)}
          className="w-7 h-7 rounded-full border border-gray-300 text-gray-600 font-bold flex items-center justify-center text-sm"
        >
          −
        </button>
        <span className="w-5 text-center text-sm font-semibold text-gray-800">{item.quantity}</span>
        <button
          onClick={() => onQtyChange(1)}
          className="w-7 h-7 rounded-full bg-amber-500 text-white font-bold flex items-center justify-center text-sm"
        >
          +
        </button>
      </div>
      <p className="text-sm font-semibold text-amber-700 w-16 text-right flex-shrink-0">
        {(item.unitPrice * item.quantity).toLocaleString()}원
      </p>
    </div>
  )
}

/** 옵션 선택 모달 — option_groups를 동적으로 렌더링 */
function MiddleOptionModal({ menu, previewSelections = [], initialQuantity = 1, editing = false, onClose, onConfirm, onLog }) {
  const openedAtRef = useRef(performance.now())
  const [selections, setSelections] = useState(() => {
    const init = {}
    const preview = previewSelections || []
    for (const g of menu.option_groups || []) {
      const idsInGroup = g.items.map((i) => i.id)
      const previewInGroup = preview.filter((id) => idsInGroup.includes(id))
      if (previewInGroup.length > 0) {
        init[g.id] = g.max_select === 1 ? previewInGroup.slice(-1) : previewInGroup
      } else {
        init[g.id] = g.items.filter((i) => i.is_default).map((i) => i.id)
      }
    }
    return init
  })
  const [quantity, setQuantity] = useState(initialQuantity)

  useEffect(() => {
    if (!previewSelections || previewSelections.length === 0) return
    setSelections((prev) => {
      const next = { ...prev }
      for (const g of menu.option_groups || []) {
        const idsInGroup = g.items.map((i) => i.id)
        const previewInGroup = previewSelections.filter((id) => idsInGroup.includes(id))
        if (previewInGroup.length > 0) {
          next[g.id] = g.max_select === 1 ? previewInGroup.slice(-1) : previewInGroup
        }
      }
      return next
    })
  }, [previewSelections, menu])

  const extraSum = useMemo(() => {
    let sum = 0
    for (const g of menu.option_groups || []) {
      for (const itemId of selections[g.id] || []) {
        const oi = g.items.find((i) => i.id === itemId)
        if (oi) sum += oi.extra_price
      }
    }
    return sum
  }, [menu, selections])

  const unitPrice = menu.price + extraSum

  const isValid = useMemo(() => {
    for (const g of menu.option_groups || []) {
      const selected = selections[g.id] || []
      if (g.is_required && selected.length < g.min_select) return false
      if (selected.length > g.max_select) return false
    }
    return true
  }, [menu, selections])

  const isTemperatureGroup = (group) =>
    /온도|hot|ice|아이스|따뜻/i.test(group.name)

  const toggleOption = (group, itemId) => {
    const option = group.items.find((i) => i.id === itemId)
    setSelections((prev) => {
      const current = prev[group.id] || []
      const isSelected = current.includes(itemId)
      let next
      if (group.max_select === 1) {
        next = isSelected ? [] : [itemId]
      } else {
        if (isSelected) {
          next = current.filter((id) => id !== itemId)
        } else if (current.length < group.max_select) {
          next = [...current, itemId]
        } else {
          next = current
        }
      }
      onLog?.({
        eventType: 'option',
        actionName: isSelected ? 'option_deselect' : 'option_select',
        targetType: 'option',
        targetId: itemId,
        targetLabel: option?.name || String(itemId),
        payload: { group_name: group.name, menu_name: menu.name },
      })
      return { ...prev, [group.id]: next }
    })
  }

  const handleConfirm = () => {
    if (!isValid) return
    const selectedOptionIds = []
    const optionLabels = []
    for (const g of menu.option_groups || []) {
      for (const itemId of selections[g.id] || []) {
        const oi = g.items.find((i) => i.id === itemId)
        if (oi) { selectedOptionIds.push(itemId); optionLabels.push(getOptionDisplayName(oi.name)) }
      }
    }
    onLog?.({
      eventType: 'option',
      actionName: 'option_confirm',
      targetType: 'menu',
      targetId: menu.id,
      targetLabel: menu.name,
      payload: { selected_option_ids: selectedOptionIds, quantity, unit_price: unitPrice },
    })
    onConfirm({ selectedOptionIds, optionLabels, quantity, unitPrice })
  }

  const closeWithoutCart = () => {
    onLog?.({
      eventType: 'option',
      actionName: 'menu_detail_close',
      targetType: 'menu',
      targetId: menu.id,
      targetLabel: menu.name,
      durationMs: Math.round(performance.now() - openedAtRef.current),
      source: menu.fromRecommendation ? 'recommendation' : 'ui',
      payload: {
        added_to_cart: false,
        from_recommendation: Boolean(menu.fromRecommendation),
      },
    })
    onClose()
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
      onClick={closeWithoutCart}
    >
      <div
        className="rounded-3xl w-full max-w-lg overflow-y-auto mx-4"
        style={{ maxHeight: '80vh', paddingBottom: '16px', background: '#fff8f3' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 rounded-full" style={{ background: '#fde8d8' }} />
        </div>

        <div className="px-6 pt-3 pb-6">
          <div className="flex justify-between items-start mb-5">
            <div>
              <h3 className="text-xl font-bold" style={{ color: '#374151' }}>
                {menu.icon_emoji} {menu.name}
              </h3>
              <p className="font-bold mt-0.5 text-lg" style={{ color: '#f4a261' }}>
                {unitPrice.toLocaleString()}원
                {extraSum > 0 && (
                  <span className="text-xs font-normal ml-1" style={{ color: '#9ca3af' }}>
                    (기본 {menu.price.toLocaleString()} + 옵션 {extraSum.toLocaleString()})
                  </span>
                )}
              </p>
              {menu.description && (
                <p className="text-xs mt-1" style={{ color: '#9ca3af' }}>{menu.description}</p>
              )}
            </div>
            <button
              onClick={closeWithoutCart}
              className="text-3xl leading-none w-8 h-8 flex items-center justify-center"
              style={{ color: '#9ca3af' }}
            >×</button>
          </div>

          {(menu.option_groups || []).map((group) => {
            const isTemp = isTemperatureGroup(group)
            return (
              <div key={group.id} className="mb-5">
                <p className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#9ca3af' }}>
                  {group.name}
                  {group.is_required && <span className="normal-case ml-1" style={{ color: '#ef4444' }}>*필수</span>}
                  {group.max_select > 1 && <span className="normal-case ml-1" style={{ color: '#d1d5db' }}>(최대 {group.max_select}개)</span>}
                </p>

                {isTemp ? (
                  <div className="grid grid-cols-2 gap-3">
                    {group.items.map((item) => {
                      const isSelected = (selections[group.id] || []).includes(item.id)
                      const isHot = /hot|따뜻/i.test(item.name)
                      return (
                        <button
                          key={item.id}
                          onClick={() => toggleOption(group, item.id)}
                          className="py-4 px-3 rounded-2xl border-2 font-bold text-base transition-all flex flex-col items-center gap-1"
                          style={{
                            borderColor: isSelected ? '#f4a261' : '#fde8d8',
                            background: isSelected ? '#fff3ec' : '#fff',
                            color: isSelected ? '#c2703a' : '#6b7280',
                          }}
                        >
                          <span className="text-3xl">{isHot ? '☕' : '🧊'}</span>
                          <span>{getOptionDisplayName(item.name)}</span>
                          {item.extra_price > 0 && (
                            <span className="text-xs" style={{ color: '#9ca3af' }}>+{item.extra_price.toLocaleString()}원</span>
                          )}
                        </button>
                      )
                    })}
                  </div>
                ) : (
                  <div className="grid grid-cols-2 gap-2">
                    {group.items.map((item) => {
                      const isSelected = (selections[group.id] || []).includes(item.id)
                      return (
                        <button
                          key={item.id}
                          onClick={() => toggleOption(group, item.id)}
                          className="py-3 px-3 rounded-2xl border-2 font-medium text-sm transition-all flex flex-col items-start"
                          style={{
                            borderColor: isSelected ? '#f4a261' : '#fde8d8',
                            background: isSelected ? '#fff3ec' : '#fff',
                            color: isSelected ? '#c2703a' : '#6b7280',
                          }}
                        >
                          <span className="font-bold">{getOptionDisplayName(item.name)}</span>
                          {item.extra_price > 0 && (
                            <span className="text-xs mt-0.5" style={{ color: '#9ca3af' }}>+{item.extra_price.toLocaleString()}원</span>
                          )}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            )
          })}

          <div className="mb-6">
            <p className="text-xs font-bold uppercase tracking-wider mb-2" style={{ color: '#9ca3af' }}>수량</p>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                className="w-11 h-11 rounded-full border-2 text-xl font-bold flex items-center justify-center"
                style={{ borderColor: '#fde8d8', color: '#6b7280' }}
              >−</button>
              <span className="text-2xl font-bold w-8 text-center" style={{ color: '#374151' }}>{quantity}</span>
              <button
                onClick={() => setQuantity((q) => Math.min(10, q + 1))}
                className="w-11 h-11 rounded-full text-white text-xl font-bold flex items-center justify-center"
                style={{ background: '#f4a261' }}
              >+</button>
            </div>
          </div>

          <button
            onClick={handleConfirm}
            disabled={!isValid}
            className="w-full py-4 rounded-2xl text-lg font-bold transition-colors"
            style={{
              background: isValid ? '#f4a261' : '#e5e7eb',
              color: isValid ? '#fff' : '#9ca3af',
            }}
          >
            {isValid
              ? (editing
                  ? `옵션 변경 완료 · ${(unitPrice * quantity).toLocaleString()}원`
                  : `장바구니 담기 · ${(unitPrice * quantity).toLocaleString()}원`)
              : '필수 옵션을 선택해주세요'}
          </button>
        </div>
      </div>
    </div>
  )
}
