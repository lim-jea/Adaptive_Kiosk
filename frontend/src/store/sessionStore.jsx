// 세션 전역 상태 관리 — React Context + useReducer

import { createContext, useContext, useReducer } from 'react'

function readStoredState() {
  if (typeof window === 'undefined') return {}
  try {
    const sessionUuid = sessionStorage.getItem('session_uuid')
    const profile = JSON.parse(sessionStorage.getItem('kiosk_profile') || '{}')
    const orderType = sessionStorage.getItem('order_type')
    return {
      sessionUuid: sessionUuid || null,
      ageGroup: profile.ageGroup || null,
      gender: profile.gender || null,
      ageEst: profile.ageEst ?? null,
      isSimpleMode: Boolean(profile.isSimpleMode),
      orderType: orderType || null,
    }
  } catch {
    return {}
  }
}

function persistProfile(nextState) {
  if (typeof window === 'undefined') return
  sessionStorage.setItem('kiosk_profile', JSON.stringify({
    ageGroup: nextState.ageGroup,
    gender: nextState.gender,
    ageEst: nextState.ageEst,
    isSimpleMode: nextState.isSimpleMode,
  }))
}

// 초기 상태
const baseState = {
  sessionUuid: null,      // 백엔드 session_uuid (32자 hex)
  ageGroup: null,         // 어린이/청년/중장년/노년
  gender: null,           // male/female/unknown
  ageEst: null,
  isSimpleMode: false,
  orderType: null,        // 'dine-in' | 'pickup'
  editCartItemId: null,   // 옵션 편집 대상 장바구니 항목 ID
  editCartSource: null,   // 'cart_review' (네비게이션 후 cart-review 로 복귀) | 'cart_panel' (KioskPage 내부 패널, 복귀 안 함)
  cart: [],
  // cart item 구조:
  // {
  //   cartItemId,         // menuName + 옵션 조합 키
  //   menuName,           // 백엔드에 보낼 식별자
  //   displayName,        // 화면 표시용 (보통 menuName과 동일)
  //   basePrice,          // 메뉴 기본가
  //   unitPrice,          // 옵션 적용된 단가
  //   quantity,
  //   selectedOptions,    // [{ option_item_id }]
  //   optionLabels,       // ["Tall", "ICE"] 표시용
  // }
}

const initialState = {
  ...baseState,
  ...readStoredState(),
}

const ACTIONS = {
  SET_SESSION: 'SET_SESSION',
  SET_VISION: 'SET_VISION',
  SET_ORDER_TYPE: 'SET_ORDER_TYPE',
  REPLACE_CART: 'REPLACE_CART',
  ADD_TO_CART: 'ADD_TO_CART',
  REMOVE_FROM_CART: 'REMOVE_FROM_CART',
  UPDATE_CART_QTY: 'UPDATE_CART_QTY',
  SET_EDIT_TARGET: 'SET_EDIT_TARGET',
  REPLACE_CART_ITEM: 'REPLACE_CART_ITEM',
  CLEAR_CART: 'CLEAR_CART',
  CLEAR_SESSION: 'CLEAR_SESSION',
}

function sessionReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_SESSION:
      if (action.payload.sessionUuid) {
        sessionStorage.setItem('session_uuid', action.payload.sessionUuid)
      }
      return {
        ...state,
        sessionUuid: action.payload.sessionUuid ?? state.sessionUuid,
      }

    case ACTIONS.SET_VISION: {
      const nextState = {
        ...state,
        ageGroup: action.payload.ageGroup ?? state.ageGroup,
        gender: action.payload.gender ?? state.gender,
        ageEst: action.payload.ageEst ?? state.ageEst,
        isSimpleMode: action.payload.isSimpleMode ?? state.isSimpleMode,
      }
      persistProfile(nextState)
      return nextState
    }

    case ACTIONS.SET_ORDER_TYPE:
      if (action.payload.orderType) {
        sessionStorage.setItem('order_type', action.payload.orderType)
      }
      return { ...state, orderType: action.payload.orderType }

    case ACTIONS.REPLACE_CART:
      return {
        ...state,
        cart: action.payload.cart ?? [],
      }

    case ACTIONS.ADD_TO_CART: {
      const newItem = action.payload
      const existing = state.cart.find((item) => item.cartItemId === newItem.cartItemId)
      if (existing) {
        return {
          ...state,
          cart: state.cart.map((item) =>
            item.cartItemId === newItem.cartItemId
              ? {
                  ...item,
                  quantity: item.quantity + newItem.quantity,
                  fromRecommendation: Boolean(item.fromRecommendation || newItem.fromRecommendation),
                }
              : item
          ),
        }
      }
      return { ...state, cart: [...state.cart, newItem] }
    }

    case ACTIONS.REMOVE_FROM_CART:
      return {
        ...state,
        cart: state.cart.filter((item) => item.cartItemId !== action.payload.cartItemId),
      }

    case ACTIONS.UPDATE_CART_QTY: {
      const { cartItemId, quantity } = action.payload
      if (quantity <= 0) {
        return {
          ...state,
          cart: state.cart.filter((item) => item.cartItemId !== cartItemId),
        }
      }
      return {
        ...state,
        cart: state.cart.map((item) =>
          item.cartItemId === cartItemId ? { ...item, quantity } : item
        ),
      }
    }

    case ACTIONS.SET_EDIT_TARGET:
      return {
        ...state,
        editCartItemId: action.payload?.cartItemId ?? null,
        editCartSource: action.payload?.source ?? (action.payload?.cartItemId ? 'cart_review' : null),
      }

    case ACTIONS.REPLACE_CART_ITEM: {
      // 옵션 편집 흐름: 기존 항목을 제거하고 신규 항목을 추가한다.
      // ⚠️ cartItemId 는 서버 GET 시마다 새 uuid 로 갱신되어 클라이언트 보관 ID 와 불일치할 수 있다.
      //    그래서 1차 매칭은 cartItemId, 실패 시 (menuName + 정렬된 option_item_ids) 로 폴백.
      const { oldCartItemId, oldMatch, newItem } = action.payload
      const sortedTargetOptionIds = (oldMatch?.optionItemIds || []).slice().sort().join('-')
      const sameContent = (item) => {
        if (!oldMatch?.menuName) return false
        if (item.menuName !== oldMatch.menuName) return false
        const itemOptionIds = (item.selectedOptions || []).map((o) => o.option_item_id).slice().sort().join('-')
        return itemOptionIds === sortedTargetOptionIds
      }
      // 폴백 매칭은 컨텐츠가 동일한 첫 항목만 제거 (동일 옵션 조합이 여러 라인 있을 일은 거의 없음).
      let removed = false
      const withoutOld = state.cart.filter((item) => {
        if (!removed && item.cartItemId === oldCartItemId) { removed = true; return false }
        if (!removed && sameContent(item)) { removed = true; return false }
        return true
      })
      const collision = withoutOld.find((item) => item.cartItemId === newItem.cartItemId)
      if (collision) {
        return {
          ...state,
          cart: withoutOld.map((item) =>
            item.cartItemId === newItem.cartItemId
              ? {
                  ...item,
                  quantity: item.quantity + newItem.quantity,
                  fromRecommendation: Boolean(item.fromRecommendation || newItem.fromRecommendation),
                }
              : item
          ),
          editCartItemId: null,
          editCartSource: null,
        }
      }
      return { ...state, cart: [...withoutOld, newItem], editCartItemId: null, editCartSource: null }
    }

    case ACTIONS.CLEAR_CART:
      return { ...state, cart: [] }

    case ACTIONS.CLEAR_SESSION:
      sessionStorage.removeItem('session_uuid')
      sessionStorage.removeItem('kiosk_profile')
      sessionStorage.removeItem('order_type')
      sessionStorage.removeItem('face_consent_at')
      sessionStorage.removeItem('session_access_token')
      sessionStorage.removeItem('session_access_token_expires_at')
      return baseState

    default:
      return state
  }
}

const SessionContext = createContext(null)

export function SessionProvider({ children }) {
  const [state, dispatch] = useReducer(sessionReducer, initialState)
  return (
    <SessionContext.Provider value={{ state, dispatch, ACTIONS }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const context = useContext(SessionContext)
  if (!context) {
    throw new Error('useSession은 SessionProvider 안에서 사용해야 합니다.')
  }
  return context
}
