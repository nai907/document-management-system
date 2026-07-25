import client from './client'

export async function exportBackup() {
  const response = await client.get('/backup/export/', { responseType: 'blob' })
  const disposition = response.headers['content-disposition'] || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : 'docmanage-backup.zip'

  const blobUrl = window.URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(blobUrl)

  return filename
}

export function importBackup(file) {
  const form = new FormData()
  form.append('file', file)
  return client.post('/backup/import/', form).then((r) => r.data)
}
