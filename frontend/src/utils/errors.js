export function extractErrorMessage(error) {
  const data = error?.response?.data
  if (!data) return error?.message || 'Something went wrong.'
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  const parts = []
  for (const [field, value] of Object.entries(data)) {
    const text = Array.isArray(value) ? value.join(' ') : String(value)
    parts.push(field === 'non_field_errors' ? text : `${field}: ${text}`)
  }
  return parts.join(' | ') || 'Something went wrong.'
}
