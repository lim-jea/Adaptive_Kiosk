// 세션 전역 상태 관리 — React Context + useReducer

import { createContext, useContext, useReducer } from 'react'

// 초기 상태
const initialState = {
  sessionUuid: null,      // 백엔드 session_uuid (32자 hex)
  ageGroup: null,         // 어린이/청년/중장년/노년
  gender: null,           // male/female/unknown
  ageEst: null,
  isSimpleMode: false,
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

const ACTIONS = {
  SET_SESSION: 'SET_SESSION',
  SET_VISION: 'SET_VISION',
  ADD_TO_CART: 'ADD_TO_CART',
  REMOVE_FROM_CART: 'REMOVE_FROM_CART',
  UPDATE_CART_QTY: 'UPDATE_CART_QTY',
  CLEAR_CART: 'CLEAR_CART',
  CLEAR_SESSION: 'CLEAR_SESSION',
}

function sessionReducer(state, action) {
  switch (action.type) {
    case ACTIONS.SET_SESSION:
      return {
        ...state,
        sessionUuid: action.payload.sessionUuid ?? state.sessionUuid,
      }

    case ACTIONS.SET_VISION:
      return {
        ...state,
        ageGroup: action.payload.ageGroup ?? state.ageGroup,
        gender: action.payload.gender ?? state.gender,
        ageEst: action.payload.ageEst ?? state.ageEst,
        isSimpleMode: action.payload.isSimpleMode ?? state.isSimpleMode,
      }

    case ACTIONS.ADD_TO_CART: {
      const newItem = action.payload
      const existing = state.cart.find((item) => item.cartItemId === newItem.cartItemId)
      if (existing) {
        return {
          ...state,
          cart: state.cart.map((item) =>
            item.cartItemId === newItem.cartItemId
              ? { ...item, quantity: item.quantity + newItem.quantity }
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

    case ACTIONS.CLEAR_CART:
      return { ...state, cart: [] }

    case ACTIONS.CLEAR_SESSION:
      sessionStorage.removeItem('session_uuid')
      return initialState

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
