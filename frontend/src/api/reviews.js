import client from './client'

export function listMyReviews() {
  return client.get('/reviews/mine/').then((r) => r.data)
}
