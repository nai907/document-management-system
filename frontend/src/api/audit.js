import client from './client'

export function listAuditLog(params = {}) {
  return client.get('/audit/', { params }).then((r) => r.data)
}

export function dashboardSummary() {
  return client.get('/dashboard/summary/').then((r) => r.data)
}
