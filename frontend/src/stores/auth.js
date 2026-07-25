import { defineStore } from 'pinia'
import * as authApi from '../api/auth'
import { loadPersistedRefreshToken, setAuthFailureHandler, setTokens } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    ready: false,
  }),
  getters: {
    isAuthenticated: (state) => !!state.user,
    isAdmin: (state) => !!state.user && state.user.role === 'admin',
  },
  actions: {
    async login(username, password) {
      const tokens = await authApi.login(username, password)
      setTokens(tokens)
      this.user = await authApi.fetchMe()
    },
    logout() {
      setTokens(null)
      this.user = null
    },
    async restoreSession() {
      setAuthFailureHandler(() => {
        this.user = null
      })
      const refresh = loadPersistedRefreshToken()
      if (!refresh) {
        this.ready = true
        return
      }
      try {
        const { access } = await authApi.refreshAccessToken(refresh)
        setTokens({ access, refresh })
        this.user = await authApi.fetchMe()
      } catch {
        setTokens(null)
        this.user = null
      } finally {
        this.ready = true
      }
    },
  },
})
