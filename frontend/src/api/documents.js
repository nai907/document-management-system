import client from './client'

export function listDocuments(params = {}) {
  return client.get('/documents/', { params }).then((r) => r.data)
}

export function getDocument(id) {
  return client.get(`/documents/${id}/`).then((r) => r.data)
}

export function createDocument({ title, description, folder, tagNames, file, changeNote }) {
  const form = new FormData()
  form.append('title', title)
  if (description) form.append('description', description)
  if (folder) form.append('folder', folder)
  if (changeNote) form.append('change_note', changeNote)
  ;(tagNames || []).forEach((t) => form.append('tag_names', t))
  form.append('file', file)
  return client.post('/documents/', form).then((r) => r.data)
}

export function updateDocument(id, payload) {
  return client.patch(`/documents/${id}/`, payload).then((r) => r.data)
}

export function deleteDocument(id) {
  return client.delete(`/documents/${id}/`)
}

export function uploadVersion(id, file, changeNote) {
  const form = new FormData()
  form.append('file', file)
  if (changeNote) form.append('change_note', changeNote)
  return client.post(`/documents/${id}/versions/`, form).then((r) => r.data)
}

function downloadPath(id, version) {
  const base = `/documents/${id}/download/`
  return version ? `${base}?version=${version}` : base
}

export async function downloadFile(id, version, filenameHint) {
  const response = await client.get(downloadPath(id, version), { responseType: 'blob' })
  const blobUrl = window.URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filenameHint || 'download'
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(blobUrl)
}

export function listPermissions(id) {
  return client.get(`/documents/${id}/permissions/`).then((r) => r.data)
}

export function grantPermission(id, payload) {
  return client.post(`/documents/${id}/permissions/`, payload).then((r) => r.data)
}

export function revokePermission(id, permId) {
  return client.delete(`/documents/${id}/permissions/${permId}/`)
}

export function getDocumentAudit(id) {
  return client.get(`/documents/${id}/audit/`).then((r) => r.data)
}

export function submitForReview(id, reviewerIds) {
  return client.post(`/documents/${id}/submit-for-review/`, { reviewer_ids: reviewerIds }).then((r) => r.data)
}

export function reviewDecision(id, decision, comment) {
  return client.post(`/documents/${id}/review-decision/`, { decision, comment }).then((r) => r.data)
}

export function listFolders() {
  return client.get('/folders/').then((r) => r.data)
}

export function folderTree() {
  return client.get('/folders/tree/').then((r) => r.data)
}

export function createFolder(payload) {
  return client.post('/folders/', payload).then((r) => r.data)
}
