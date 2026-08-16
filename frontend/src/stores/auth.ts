import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { authApi } from '../services/auth'

interface User {
  id: number
  email: string
  username: string
  full_name?: string
  is_active: boolean
  is_superuser: boolean
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null

  // Actions
  login: (username: string, password: string) => Promise<void>
  register: (email: string, username: string, password: string, fullName?: string) => Promise<void>
  logout: () => void
  fetchUser: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await authApi.login(username, password)
          const { access_token } = response.data
          set({ token: access_token, isAuthenticated: true })
          // 获取用户信息
          await get().fetchUser()
          set({ isLoading: false })
        } catch (error: any) {
          const message = error.response?.data?.detail || '登录失败'
          set({ error: message, isLoading: false })
          throw error
        }
      },

      register: async (email: string, username: string, password: string, fullName?: string) => {
        set({ isLoading: true, error: null })
        try {
          await authApi.register(email, username, password, fullName)
          set({ isLoading: false })
        } catch (error: any) {
          const message = error.response?.data?.detail || '注册失败'
          set({ error: message, isLoading: false })
          throw error
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
          error: null,
        })
      },

      fetchUser: async () => {
        try {
          const response = await authApi.getCurrentUser()
          set({ user: response.data, isAuthenticated: true })
        } catch (error) {
          set({ user: null, token: null, isAuthenticated: false })
        }
      },

      clearError: () => {
        set({ error: null })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
