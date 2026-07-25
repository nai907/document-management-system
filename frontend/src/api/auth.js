import client from './client'

export function login(username, password) {
  return client.post('/auth/token/', { username, password }).then((r) => r.data)
}

export function refreshAccessToken(refresh) {
  return client.post('/auth/token/refresh/', { refresh }).then((r) => r.data)
}

export function fetchMe() {
  return client.get('/auth/me/').then((r) => r.data)
}

export function listUsers() {
  return client.get('/users/').then((r) => r.data)
}

export function createUser(payload) {
  return client.post('/users/', payload).then((r) => r.data)
}

export function updateUser(id, payload) {
  return client.patch(`/users/${id}/`, payload).then((r) => r.data)
}
