// 키오스크 메인 페이지 — 메뉴 동적 로드 + 옵션 모달 + 장바구니
// 메뉴/카테고리/옵션은 모두 백엔드 API에서 동적으로 가져옴

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { useSession } from '../store/sessionStore.jsx'

export default function KioskPage() {
  const navigate = useNavigate()
  const { state, dispatch, ACTIONS } = useSession()

  const [categories, setCategories] = useState([])
  const [menus, setMenus] = useState([])
  const [activeCategory, setActiveCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [optionMenu, setOptionMenu] = useState(null)
  const [cartOpen, setCartOpen] = useState(false)

  // 마운트 시 카테고리 + 메뉴 동시 로드
  useEffect(() => {
    const loadAll = async () => {
      try {
        const [catRes, menuRes] = await Promise.all([
          api.get('/api/v1/categories', { params: { limit: 1000 } }),
          api.get('/api/v1/menus', { params: { limit: 1000 } }),
        ])
        setCategories(catRes.data.items || [])
        setMenus(menuRes.data.items || [])
      } catch (err) {
        console.error('메뉴 로드 실패:', err)
      } finally {
        setLoading(false)
      }
    }
    loadAll()
  }, [])

  const filteredMenus = useMemo(() => {
    if (activeCategory === 'all') return menus
    return menus.filter((m) => m.category === activeCategory)
  }, [menus, activeCategory])

  const totalPrice = state.cart.reduce((sum, item) => sum + item.unitPrice * item.quantity, 0)
  const totalCount = state.cart.reduce((sum, item) => sum + item.quantity, 0)

  // 메뉴 클릭 → 상세 (옵션 그룹 포함) 조회 후 모달 오픈
  const handleMenuClick = useCallback(async (menu) => {
    try {
      const detailRes = await api.get(`/api/v1/menus/${encodeURIComponent(menu.name)}`)
      setOptionMenu(detailRes.data)
    } catch (err) {
      console.error('메뉴 상세 로드 실패:', err)
    }
  }, [])

  const handleConfirmOption = useCallback(({ selectedOptionIds, optionLabels, quantity, unitPrice }) => {
    const cartItemId = `${optionMenu.name}_${[...selectedOptionIds].sort().join('-')}`
    dispatch({
      type: ACTIONS.ADD_TO_CART,
      payload: {
        cartItemId,
        menuName: optionMenu.name,
        displayName: optionMenu.name,
        basePrice: optionMenu.price,
        unitPrice,
        quantity,
        selectedOptions: selectedOptionIds.map((id) => ({ option_item_id: id })),
        optionLabels,
      },
    })
    setOptionMenu(null)
    setCartOpen(true)
  }, [optionMenu, dispatch, ACTIONS])

  const handleQtyChange = useCallback((cartItemId, delta) => {
    const item = state.cart.find((i) => i.cartItemId === cartItemId)
    if (!item) return
    dispatch({
      type: ACTIONS.UPDATE_CART_QTY,
      payload: { cartItemId, quantity: item.quantity + delta },
    })
  }, [state.cart, dispatch, ACTIONS])

  const handleOrder = useCallback(() => {
    if (state.cart.length === 0 || !state.sessionUuid) return
    navigate('/payment')
  }, [state.cart, state.sessionUuid, navigate])

  const handleBack = useCallback(() => {
    navigate('/')
  }, [navigate])

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 헤더 */}
      <header className="bg-white shadow-sm px-4 py-3 flex items-center justify-between sticky top-0 z-10">
        <button onClick={handleBack} className="text-gray-500 hover:text-gray-700 p-2 -ml-2">
          ← 뒤로
        </button>
        <h1 className="text-lg font-bold text-amber-900">메뉴 주문</h1>
        <div className="w-10" />
      </header>

      {/* 카테고리 탭 (동적) */}
      <div className="bg-white border-b flex overflow-x-auto sticky top-[56px] z-10">
        <CategoryTab
          label="전체"
          active={activeCategory === 'all'}
          onClick={() => setActiveCategory('all')}
        />
        {categories.map((cat) => (
          <CategoryTab
            key={cat.id}
            label={cat.name}
            active={activeCategory === cat.name}
            onClick={() => setActiveCategory(cat.name)}
          />
        ))}
      </div>

      {/* 메뉴 그리드 */}
      <div className="flex-1 p-4 pb-40">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-8 h-8 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filteredMenus.length === 0 ? (
          <p className="text-center text-gray-400 mt-12">해당 카테고리 메뉴가 없습니다</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {filteredMenus.map((menu) => (
              <MenuCard
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
      </div>

      {/* 하단 장바구니 바 */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg z-20">
        {cartOpen && state.cart.length > 0 && (
          <div className="max-h-56 overflow-y-auto border-b divide-y bg-gray-50">
            {state.cart.map((item) => (
              <CartRow
                key={item.cartItemId}
                item={item}
                onQtyChange={(delta) => handleQtyChange(item.cartItemId, delta)}
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
              ${state.cart.length > 0
                ? 'border-amber-400 text-amber-600 hover:bg-amber-50'
                : 'border-gray-200 text-gray-300 cursor-not-allowed'}`}
          >
            <span className="text-xl">🛒</span>
            {totalCount > 0 && (
              <span className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-amber-500 text-white text-xs font-bold flex items-center justify-center">
                {totalCount > 9 ? '9+' : totalCount}
              </span>
            )}
          </button>

          <button
            onClick={handleOrder}
            disabled={state.cart.length === 0}
            className={`flex-1 min-h-[48px] py-3 rounded-2xl text-base font-bold transition-colors
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

      {/* 옵션 선택 모달 */}
      {optionMenu && (
        <OptionModal
          menu={optionMenu}
          onClose={() => setOptionMenu(null)}
          onConfirm={handleConfirmOption}
        />
      )}
    </div>
  )
}

/** 카테고리 탭 */
function CategoryTab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex-shrink-0 px-5 py-3 text-sm font-medium border-b-2 transition-colors
        ${active
          ? 'border-amber-500 text-amber-700'
          : 'border-transparent text-gray-500 hover:text-gray-700'}`}
    >
      {label}
    </button>
  )
}

/** 메뉴 카드 */
function MenuCard({ menu, cartCount, onClick }) {
  return (
    <button
      onClick={onClick}
      className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden text-left active:scale-95 transition-transform w-full"
    >
      <div className="relative h-28 bg-amber-50 flex items-center justify-center text-5xl">
        {menu.image_url
          ? <img src={menu.image_url} alt={menu.name} className="h-full w-full object-cover" />
          : (menu.icon_emoji || '🍽️')}
        {cartCount > 0 && (
          <span className="absolute top-2 right-2 w-6 h-6 rounded-full bg-amber-500 text-white text-xs font-bold flex items-center justify-center shadow">
            {cartCount}
          </span>
        )}
      </div>
      <div className="p-3">
        <p className="font-semibold text-gray-800 text-sm leading-tight mb-1 line-clamp-1">{menu.name}</p>
        {menu.description && (
          <p className="text-xs text-gray-400 mb-1 line-clamp-1">{menu.description}</p>
        )}
        <p className="text-amber-600 font-bold text-sm">{menu.price.toLocaleString()}원~</p>
      </div>
    </button>
  )
}

/** 장바구니 행 */
function CartRow({ item, onQtyChange }) {
  const optionLabel = (item.optionLabels || []).join(' · ')
  return (
    <div className="flex items-center px-4 py-2.5 gap-3 bg-white">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">{item.displayName}</p>
        {optionLabel && <p className="text-xs text-gray-400">{optionLabel}</p>}
      </div>
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
function OptionModal({ menu, onClose, onConfirm }) {
  const [selections, setSelections] = useState(() => {
    const init = {}
    for (const g of menu.option_groups || []) {
      init[g.id] = g.items.filter((i) => i.is_default).map((i) => i.id)
    }
    return init
  })
  const [quantity, setQuantity] = useState(1)

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

  const toggleOption = (group, itemId) => {
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
        if (oi) {
          selectedOptionIds.push(itemId)
          optionLabels.push(oi.name)
        }
      }
    }
    onConfirm({ selectedOptionIds, optionLabels, quantity, unitPrice })
  }

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-end justify-center"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-t-3xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        style={{ paddingBottom: 'env(safe-area-inset-bottom, 16px)' }}
      >
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 bg-gray-300 rounded-full" />
        </div>

        <div className="px-6 pt-3 pb-6">
          <div className="flex justify-between items-start mb-5">
            <div>
              <h3 className="text-xl font-bold text-gray-800">
                {menu.icon_emoji} {menu.name}
              </h3>
              <p className="text-amber-600 font-bold mt-0.5 text-lg">
                {unitPrice.toLocaleString()}원
                {extraSum > 0 && (
                  <span className="text-xs text-gray-400 font-normal ml-1">
                    (기본 {menu.price.toLocaleString()} + 옵션 {extraSum.toLocaleString()})
                  </span>
                )}
              </p>
              {menu.description && (
                <p className="text-xs text-gray-400 mt-1">{menu.description}</p>
              )}
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-3xl leading-none w-8 h-8 flex items-center justify-center"
            >
              ×
            </button>
          </div>

          {(menu.option_groups || []).map((group) => (
            <div key={group.id} className="mb-5">
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                {group.name}
                {group.is_required && <span className="text-red-400 normal-case ml-1">*필수</span>}
                {group.max_select > 1 && (
                  <span className="text-gray-300 normal-case ml-1">
                    (최대 {group.max_select}개)
                  </span>
                )}
              </p>
              <div className="grid grid-cols-2 gap-2">
                {group.items.map((item) => {
                  const isSelected = (selections[group.id] || []).includes(item.id)
                  return (
                    <button
                      key={item.id}
                      onClick={() => toggleOption(group, item.id)}
                      className={`py-3 px-3 rounded-2xl border-2 font-medium text-sm transition-all flex flex-col items-start
                        ${isSelected
                          ? 'border-amber-500 bg-amber-50 text-amber-700'
                          : 'border-gray-200 text-gray-600 hover:border-gray-300 bg-white'}`}
                    >
                      <span className="font-bold">{item.name}</span>
                      {item.extra_price > 0 && (
                        <span className="text-xs text-gray-400 mt-0.5">
                          +{item.extra_price.toLocaleString()}원
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}

          <div className="mb-6">
            <p className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">수량</p>
            <div className="flex items-center gap-4">
              <button
                onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                className="w-11 h-11 rounded-full border-2 border-gray-200 text-gray-700 text-xl font-bold flex items-center justify-center hover:border-gray-400 transition-colors"
              >
                −
              </button>
              <span className="text-2xl font-bold text-gray-800 w-8 text-center">{quantity}</span>
              <button
                onClick={() => setQuantity((q) => Math.min(10, q + 1))}
                className="w-11 h-11 rounded-full bg-amber-500 text-white text-xl font-bold flex items-center justify-center hover:bg-amber-600 transition-colors"
              >
                +
              </button>
            </div>
          </div>

          <button
            onClick={handleConfirm}
            disabled={!isValid}
            className={`w-full py-4 rounded-2xl text-lg font-bold transition-colors
              ${isValid
                ? 'bg-amber-500 hover:bg-amber-600 active:bg-amber-700 text-white'
                : 'bg-gray-200 text-gray-400 cursor-not-allowed'}`}
          >
            {isValid
              ? `장바구니 담기 · ${(unitPrice * quantity).toLocaleString()}원`
              : '필수 옵션을 선택해주세요'}
          </button>
        </div>
      </div>
    </div>
  )
}
