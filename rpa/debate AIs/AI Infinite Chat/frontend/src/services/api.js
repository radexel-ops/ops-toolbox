import { API_BASE_URL } from '../config'

const API_BASE = `${API_BASE_URL}/api`

export async function fetchModels() {
  const response = await fetch(`${API_BASE}/models`)
  if (!response.ok) throw new Error('Failed to fetch models')
  return response.json()
}

export async function updateApiKey(provider, apiKey) {
  // 백엔드는 { openai: "key", google: "key", ... } 형태를 기대
  const body = { [provider]: apiKey }
  const response = await fetch(`${API_BASE}/settings/api-keys`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!response.ok) throw new Error('Failed to update API key')
  return response.json()
}

export async function getSettings() {
  const response = await fetch(`${API_BASE}/settings`)
  if (!response.ok) throw new Error('Failed to fetch settings')
  return response.json()
}
