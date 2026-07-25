import axios from 'axios'

const client = axios.create({ baseURL: '/api' })

let accessToken = null
let refreshToken = null
let onAuthFailure = () => {}

export function setTokens(tokens) {
  accessToken = tokens?.access ?? null
  refreshToken = tokens?.refresh ?? null
  if (accessToken) {
    sessionStorage.setItem('dms_refresh', refreshToken)
  } else {
    sessionStorage.removeItem('dms_refresh')
  }
}

export function loadPersistedRefreshToken() {
  return sessionStorage.getItem('dms_refresh')
}

export function setAuthFailureHandler(handler) {
  onAuthFailure = handler
}

client.interceptors.request.use((config) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

let refreshing = null

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response, config } = error
    if (response && response.status === 401 && !config._retried && refreshToken) {
      config._retried = true
      try {
        refreshing = refreshing || axios.post('/api/auth/token/refresh/', { refresh: refreshToken })
        const { data } = await refreshing
        refreshing = null
        setTokens({ access: data.access, refresh: refreshToken })
        config.headers.Authorization = `Bearer ${data.access}`
        return client(config)
      } catch (refreshError) {
        refreshing = null
        onAuthFailure()
        return Promise.reject(refreshError)
      }
    }
    if (response && response.status === 401) {
      onAuthFailure()
    }
    return Promise.reject(error)
  }
)

export default client
