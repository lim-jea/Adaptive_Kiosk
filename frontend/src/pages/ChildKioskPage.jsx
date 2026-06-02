import { useEffect, useRef, useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api, { logClientTiming } from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'
import { useLogger } from '../hooks/useLogger'
import CartScrollHint from '../components/CartScrollHint'

function normalizeOptionIds(optionIds = []) {
  return [...optionIds].map(Number).filter(Boolean).sort((a, b) => a - b)
}

export default function ChildKioskPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()
  const logger = useLogger(state.sessionUuid)

  const [categories, setCategories] = useState([])
  const [menus, setMenus] = useState([])
  const [activeCategory, setActiveCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [optionMenu, setOptionMenu] = useState(null)
  const [cartOpen, setCartOpen] = useState(true)

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

  // 서버 cart 응답에는 image/emoji 가 없음 — 현재 로드된 menus 에서 조회해 복원.
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
      menuEmoji: menuMeta?.icon_emoji || '🍽️',
    }
  }), [menus])

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

        logClientTiming('child_kiosk.loadMenusAndCategories', performance.now() - startedAt, {
          category_count: (catRes.data.items || []).length,
          menu_count: (menuRes.data.items || []).length,
        })
      } catch (err) {
        logClientTiming('child_kiosk.loadMenusAndCategories.error', performance.now() - startedAt)
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
      logger.logScreenEnter('child_kiosk', {
        is_simple_mode: state.isSimpleMode,
      })
    }

    return () => {
      if (state.sessionUuid) {
        logger.logScreenExit('child_kiosk', Date.now() - enteredAt)
      }
    }
  }, [logger, state.sessionUuid, state.isSimpleMode])

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

        logClientTiming('child_kiosk.loadServerCart', performance.now() - startedAt, {
          item_count: localCart.length,
        })
      } catch (err) {
        logClientTiming('child_kiosk.loadServerCart.error', performance.now() - startedAt)
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

        logClientTiming('child_kiosk.syncCartToServer', performance.now() - startedAt, {
          item_count: state.cart.length,
        })
      } catch (err) {
        logClientTiming('child_kiosk.syncCartToServer.error', performance.now() - startedAt, {
          item_count: state.cart.length,
        })
        console.error('서버 장바구니 동기화 실패:', err)
      }
    }

    syncCartToServer()
  }, [state.sessionUuid, state.cart, serializeCartForSync])

  const filteredMenus = useMemo(() => {
    const list = activeCategory === 'all'
      ? menus
      : menus.filter((menu) => menu.category === activeCategory)

    return [...list].sort((a, b) => {
      const childKeywords = ['초코', '딸기', '망고', '스무디', '에이드', '주스', '라떼']
      const aScore = childKeywords.some((keyword) => a.name.includes(keyword)) ? 0 : 1
      const bScore = childKeywords.some((keyword) => b.name.includes(keyword)) ? 0 : 1
      return aScore - bScore
    })
  }, [menus, activeCategory])

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)

  const handleCategoryChange = useCallback((categoryName) => {
    logger.log('navigation', 'child_kiosk', {
      actionName: 'category_tab_click',
      targetType: 'category',
      targetLabel: categoryName,
    })

    setActiveCategory(categoryName)
  }, [logger])

  const handleMenuClick = useCallback(async (menu) => {
    logger.log('click', 'child_kiosk', {
      actionName: 'menu_click',
      targetType: 'menu',
      targetId: menu.id,
      targetLabel: menu.name,
    })

    const startedAt = performance.now()

    try {
      const detailRes = await api.get(`/api/v1/menus/${encodeURIComponent(menu.name)}`)

      setOptionMenu({
        ...detailRes.data,
        fromRecommendation: false,
      })

      logClientTiming('child_kiosk.loadMenuDetail', performance.now() - startedAt, {
        menu_name: menu.name,
      })
    } catch (err) {
      logClientTiming('child_kiosk.loadMenuDetail.error', performance.now() - startedAt, {
        menu_name: menu.name,
      })

      console.error('메뉴 상세 로드 실패:', err)
    }
  }, [logger])

  const handleConfirmOption = useCallback(({ selectedOptionIds, optionLabels, quantity, unitPrice }) => {
    if (!optionMenu) return

    const cartItemId = `${optionMenu.name}_${normalizeOptionIds(selectedOptionIds).join('-')}`
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
      menuEmoji: optionMenu.icon_emoji || '🍽️',
    }

    logger.log('cart', 'child_kiosk', {
      actionName: isEditing ? 'cart_edit_commit' : 'cart_add',
      targetType: 'menu',
      targetId: optionMenu.id,
      targetLabel: optionMenu.name,
      payload: {
        quantity,
        option_item_ids: selectedOptionIds,
        option_labels: optionLabels,
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

    setOptionMenu(null)
    setCartOpen(true)
  }, [optionMenu, logger, dispatch, ACTIONS, navigate])

  const handleEditCartFromPanel = useCallback((item) => {
    logger.log('cart', 'child_kiosk', {
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
    const item = state.cart.find((cartItem) => cartItem.cartItemId === cartItemId)
    if (!item) return

    logger.log('cart', 'child_kiosk', {
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
      payload: {
        cartItemId,
        quantity: item.quantity + delta,
      },
    })
  }, [state.cart, logger, dispatch, ACTIONS])

  const handleOrder = useCallback(() => {
    if (state.cart.length === 0 || !state.sessionUuid) return

    logger.log('navigation', 'child_kiosk', {
      actionName: 'go_to_childpayment',
      targetType: 'button',
      targetLabel: 'childpayment',
      payload: {
        total_price: totalPrice,
        total_count: totalCount,
      },
    })

    navigate('/childpayment')
  }, [logger, navigate, state.cart.length, state.sessionUuid, totalPrice, totalCount])

  const handleBack = useCallback(() => {
    logger.log('navigation', 'child_kiosk', {
      actionName: 'back_home',
      targetType: 'button',
      targetLabel: 'home',
    })

    navigate('/')
  }, [logger, navigate])

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#ECFEFF' }}>
      <header className="px-4 py-4 flex items-center justify-between sticky top-0 z-10 shadow-sm bg-white">
        <button
          onClick={handleBack}
          className="text-sky-600 text-lg font-black px-3 py-2 rounded-2xl bg-sky-100"
        >
          ← 뒤로
        </button>

        <div className="flex items-center gap-2">
          <span className="text-3xl">🧃</span>
          <h1 className="text-xl font-black text-gray-800">어린이 주문</h1>
        </div>

        <div className="w-16" />
      </header>

      <div className="bg-white border-b flex overflow-x-auto sticky top-[64px] z-10">
        <ChildCategoryTab
          label="전체"
          active={activeCategory === 'all'}
          onClick={() => handleCategoryChange('all')}
        />

        {categories.map((category) => (
          <ChildCategoryTab
            key={category.id}
            label={category.name}
            active={activeCategory === category.name}
            onClick={() => handleCategoryChange(category.name)}
          />
        ))}
      </div>

      <div className="flex-1 p-4 pb-40">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-12 h-12 border-4 border-sky-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filteredMenus.length === 0 ? (
          <p className="text-center text-sky-500 mt-12 text-xl font-bold">
            이 카테고리에는 메뉴가 없어요
          </p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {filteredMenus.map((menu) => (
              <ChildMenuCard
                key={menu.id}
                menu={menu}
                cartCount={state.cart
                  .filter((item) => item.menuName === menu.name)
                  .reduce((sum, item) => sum + item.quantity, 0)}
                onClick={() => handleMenuClick(menu)}
              />
            ))}
          </div>
        )}
      </div>

      <div className="fixed bottom-0 left-0 right-0 bg-white border-t-4 border-sky-100 shadow-lg z-20">
        {cartOpen && state.cart.length > 0 && (
          <div className="relative border-b bg-sky-50">
            <div className="max-h-[190px] overflow-y-auto divide-y">
              {state.cart.map((item) => (
                <ChildCartRow
                  key={item.cartItemId}
                  item={item}
                  onQtyChange={(delta) => handleQtyChange(item.cartItemId, delta)}
                  onEditOptions={handleEditCartFromPanel}
                />
              ))}

              <div className="px-4 py-3 flex justify-between text-lg font-black bg-white">
                <span className="text-gray-700">합계</span>
                <span className="text-sky-600">{totalPrice.toLocaleString()}원</span>
              </div>
            </div>
            <CartScrollHint visible={state.cart.length > 2} label="아래에 메뉴가 더 있어요" />
          </div>
        )}

        <div className="px-4 py-4 flex items-center gap-3">
          <button
            onClick={() => setCartOpen((value) => !value)}
            disabled={state.cart.length === 0}
            className={`relative w-14 h-14 rounded-3xl border-4 font-black text-2xl flex items-center justify-center
              ${state.cart.length > 0
                ? 'border-sky-300 text-sky-600 bg-sky-50'
                : 'border-gray-200 text-gray-300 bg-gray-100 cursor-not-allowed'}`}
          >
            🛒

            {totalCount > 0 && (
              <span className="absolute -top-2 -right-2 w-7 h-7 rounded-full bg-pink-500 text-white text-sm font-black flex items-center justify-center">
                {totalCount > 9 ? '9+' : totalCount}
              </span>
            )}
          </button>

          <button
            onClick={handleOrder}
            disabled={state.cart.length === 0}
            className={`flex-1 min-h-[58px] rounded-3xl text-xl font-black transition-all
              ${state.cart.length > 0
                ? 'bg-sky-500 hover:bg-sky-600 text-white'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
          >
            {state.cart.length === 0
              ? '메뉴를 골라주세요'
              : `결제하기 · ${totalPrice.toLocaleString()}원`}
          </button>
        </div>
      </div>

      {optionMenu && (
        <ChildOptionModal
          menu={optionMenu}
          initialSelections={optionMenu.initialSelections || []}
          initialQuantity={optionMenu.initialQuantity || 1}
          editing={Boolean(optionMenu.editingItemId)}
          onClose={() => {
            if (optionMenu.editingItemId) {
              dispatch({ type: ACTIONS.SET_EDIT_TARGET, payload: { cartItemId: null } })
            }
            setOptionMenu(null)
          }}
          onConfirm={handleConfirmOption}
          onLog={(event) => logger.log(event.eventType, 'child_kiosk', event)}
        />
      )}
    </div>
  )
}

function ChildCategoryTab({ label, active, onClick }) {
  const ref = useRef(null)

  useEffect(() => {
    if (active && ref.current) {
      ref.current.scrollIntoView({
        behavior: 'smooth',
        inline: 'center',
        block: 'nearest',
      })
    }
  }, [active])

  return (
    <button
      ref={ref}
      onClick={onClick}
      className={`flex-shrink-0 px-6 py-4 text-lg font-black border-b-4 transition-all
        ${active
          ? 'border-sky-500 text-sky-600 bg-sky-50'
          : 'border-transparent text-gray-500 bg-white'}`}
    >
      {label}
    </button>
  )
}

function ChildMenuCard({ menu, cartCount, onClick }) {
  return (
    <button
      onClick={onClick}
      className="bg-white rounded-[28px] shadow-sm border-4 border-sky-100 overflow-hidden text-left active:scale-95 transition-all w-full"
    >
      <div className="relative overflow-hidden" style={{ paddingBottom: '90%' }}>
        <div className="absolute inset-0">
          {menu.image_url ? (
            <img
              src={menu.image_url}
              alt={menu.name}
              className="h-full w-full object-cover"
              onError={(event) => {
                event.currentTarget.style.display = 'none'
                event.currentTarget.nextSibling.style.display = 'flex'
              }}
            />
          ) : null}

          <div
            className="h-full w-full bg-sky-50 items-center justify-center text-6xl"
            style={{ display: menu.image_url ? 'none' : 'flex' }}
          >
            {menu.icon_emoji || '🍽️'}
          </div>
        </div>

        {cartCount > 0 && (
          <span className="absolute top-2 right-2 w-8 h-8 rounded-full bg-pink-500 text-white text-base font-black flex items-center justify-center shadow-lg z-10">
            {cartCount}
          </span>
        )}
      </div>

      <div className="p-4">
        <p className="font-black text-gray-800 text-lg leading-tight mb-2 line-clamp-2">
          {menu.name}
        </p>

        <p className="text-sky-600 font-black text-lg">
          {menu.price.toLocaleString()}원~
        </p>
      </div>
    </button>
  )
}

function ChildCartRow({ item, onQtyChange, onEditOptions }) {
  const optionLabel = (item.optionLabels || []).join(' · ')

  return (
    <div className="flex items-center px-4 py-3 gap-2 bg-white">
      <div className="flex-1 min-w-0">
        <p className="text-base font-black text-gray-800 truncate">{item.displayName}</p>
        {optionLabel && <p className="text-sm text-gray-400 truncate">{optionLabel}</p>}
      </div>

      {onEditOptions && (
        <button
          onClick={() => onEditOptions(item)}
          className="flex-shrink-0 px-2.5 h-8 rounded-full border-2 border-sky-300 text-sky-600 text-xs font-black hover:bg-sky-50"
        >
          옵션
        </button>
      )}

      <div className="flex items-center gap-2">
        <button
          onClick={() => onQtyChange(-1)}
          className="w-9 h-9 rounded-full border-2 border-gray-300 text-gray-600 font-black text-xl"
        >
          −
        </button>

        <span className="w-6 text-center text-lg font-black text-gray-800">{item.quantity}</span>

        <button
          onClick={() => onQtyChange(1)}
          className="w-9 h-9 rounded-full bg-sky-500 text-white font-black text-xl"
        >
          +
        </button>
      </div>

      <p className="text-base font-black text-sky-600 w-20 text-right">
        {(item.unitPrice * item.quantity).toLocaleString()}원
      </p>
    </div>
  )
}

function ChildOptionModal({ menu, initialSelections = [], initialQuantity = 1, editing = false, onClose, onConfirm, onLog }) {
  const openedAtRef = useRef(performance.now())
  const [selections, setSelections] = useState(() => {
    const init = {}
    const preview = initialSelections || []

    for (const group of menu.option_groups || []) {
      const idsInGroup = group.items.map((i) => i.id)
      const previewInGroup = preview.filter((id) => idsInGroup.includes(id))
      if (previewInGroup.length > 0) {
        init[group.id] = group.max_select === 1 ? previewInGroup.slice(-1) : previewInGroup
      } else {
        init[group.id] = group.items
          .filter((item) => item.is_default)
          .map((item) => item.id)
      }
    }

    return init
  })

  const [quantity, setQuantity] = useState(initialQuantity)

  const extraSum = useMemo(() => {
    let sum = 0

    for (const group of menu.option_groups || []) {
      for (const itemId of selections[group.id] || []) {
        const optionItem = group.items.find((item) => item.id === itemId)
        if (optionItem) sum += optionItem.extra_price
      }
    }

    return sum
  }, [menu, selections])

  const unitPrice = menu.price + extraSum

  const isValid = useMemo(() => {
    for (const group of menu.option_groups || []) {
      const selected = selections[group.id] || []

      if (group.is_required && selected.length < group.min_select) return false
      if (selected.length > group.max_select) return false
    }

    return true
  }, [menu, selections])

  const toggleOption = (group, itemId) => {
    const option = group.items.find((item) => item.id === itemId)

    setSelections((prev) => {
      const current = prev[group.id] || []
      const isSelected = current.includes(itemId)

      let next

      if (group.max_select === 1) {
        next = isSelected ? [] : [itemId]
      } else if (isSelected) {
        next = current.filter((id) => id !== itemId)
      } else if (current.length < group.max_select) {
        next = [...current, itemId]
      } else {
        next = current
      }

      onLog?.({
        eventType: 'option',
        actionName: isSelected ? 'option_deselect' : 'option_select',
        targetType: 'option',
        targetId: itemId,
        targetLabel: option?.name || String(itemId),
        payload: {
          group_name: group.name,
          menu_name: menu.name,
        },
      })

      return {
        ...prev,
        [group.id]: next,
      }
    })
  }

  const handleConfirm = () => {
    if (!isValid) return

    const selectedOptionIds = []
    const optionLabels = []

    for (const group of menu.option_groups || []) {
      for (const itemId of selections[group.id] || []) {
        const optionItem = group.items.find((item) => item.id === itemId)

        if (optionItem) {
          selectedOptionIds.push(itemId)
          optionLabels.push(optionItem.name)
        }
      }
    }

    onLog?.({
      eventType: 'option',
      actionName: 'option_confirm',
      targetType: 'menu',
      targetId: menu.id,
      targetLabel: menu.name,
      payload: {
        selected_option_ids: selectedOptionIds,
        quantity,
        unit_price: unitPrice,
      },
    })

    onConfirm({
      selectedOptionIds,
      optionLabels,
      quantity,
      unitPrice,
    })
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
      className="fixed inset-0 bg-black/50 z-50 flex items-end justify-center"
      onClick={closeWithoutCart}
    >
      <div
        className="bg-white rounded-t-[36px] w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="px-6 pt-6 pb-8">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h3 className="text-3xl font-black text-gray-800">
                {menu.icon_emoji} {menu.name}
              </h3>

              <p className="text-sky-600 font-black mt-2 text-2xl">
                {unitPrice.toLocaleString()}원
              </p>
            </div>

            <button
              onClick={closeWithoutCart}
              className="text-gray-400 text-4xl leading-none w-10 h-10 flex items-center justify-center"
            >
              ×
            </button>
          </div>

          {(menu.option_groups || []).map((group) => (
            <div key={group.id} className="mb-6">
              <p className="text-base font-black text-gray-500 mb-3">
                {group.name}
                {group.is_required && <span className="text-pink-500 ml-1">*필수</span>}
              </p>

              <div className="grid grid-cols-2 gap-3">
                {group.items.map((item) => {
                  const isSelected = (selections[group.id] || []).includes(item.id)

                  return (
                    <button
                      key={item.id}
                      onClick={() => toggleOption(group, item.id)}
                      className={`py-4 px-4 rounded-3xl border-4 text-left transition-all
                        ${isSelected
                          ? 'border-sky-400 bg-sky-50 text-sky-700'
                          : 'border-gray-100 bg-white text-gray-600'}`}
                    >
                      <p className="text-lg font-black">{item.name}</p>

                      {item.extra_price > 0 && (
                        <p className="text-sm text-gray-400 mt-1">
                          +{item.extra_price.toLocaleString()}원
                        </p>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}

          <div className="mb-6">
            <p className="text-base font-black text-gray-500 mb-3">수량</p>

            <div className="flex items-center gap-5">
              <button
                onClick={() => setQuantity((value) => Math.max(1, value - 1))}
                className="w-14 h-14 rounded-full border-4 border-gray-200 text-gray-700 text-3xl font-black"
              >
                −
              </button>

              <span className="text-4xl font-black text-gray-800 w-12 text-center">
                {quantity}
              </span>

              <button
                onClick={() => setQuantity((value) => Math.min(10, value + 1))}
                className="w-14 h-14 rounded-full bg-sky-500 text-white text-3xl font-black"
              >
                +
              </button>
            </div>
          </div>

          <button
            onClick={handleConfirm}
            disabled={!isValid}
            className={`w-full py-5 rounded-3xl text-2xl font-black transition-all
              ${isValid
                ? 'bg-sky-500 hover:bg-sky-600 text-white'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
          >
            {isValid
              ? (editing
                  ? `옵션 변경 완료 · ${(unitPrice * quantity).toLocaleString()}원`
                  : `담기 · ${(unitPrice * quantity).toLocaleString()}원`)
              : '필수 옵션을 골라주세요'}
          </button>
        </div>
      </div>
    </div>
  )
}
