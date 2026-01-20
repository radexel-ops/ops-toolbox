/**
 * Conversation Storage Service
 * IndexedDB를 사용한 대화 기록 영구 저장
 */

const DB_NAME = 'AIInfiniteChat'
const DB_VERSION = 1
const STORE_NAME = 'conversations'

let db = null

/**
 * IndexedDB 초기화
 */
export async function initDB() {
  if (db) return db

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onerror = () => {
      console.error('IndexedDB open failed:', request.error)
      reject(request.error)
    }

    request.onsuccess = () => {
      db = request.result
      resolve(db)
    }

    request.onupgradeneeded = (event) => {
      const database = event.target.result

      // conversations store 생성
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: 'id' })
        store.createIndex('createdAt', 'createdAt', { unique: false })
        store.createIndex('updatedAt', 'updatedAt', { unique: false })
      }
    }
  })
}

/**
 * 대화 저장
 */
export async function saveConversation(conversation) {
  await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)

    const data = {
      ...conversation,
      updatedAt: Date.now()
    }

    const request = store.put(data)

    request.onsuccess = () => resolve(data)
    request.onerror = () => reject(request.error)
  })
}

/**
 * 대화 불러오기
 */
export async function getConversation(id) {
  await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.get(id)

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

/**
 * 모든 대화 목록 가져오기 (최신순)
 */
export async function getAllConversations() {
  await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readonly')
    const store = transaction.objectStore(STORE_NAME)
    const index = store.index('updatedAt')
    const request = index.openCursor(null, 'prev')

    const conversations = []

    request.onsuccess = (event) => {
      const cursor = event.target.result
      if (cursor) {
        conversations.push(cursor.value)
        cursor.continue()
      } else {
        resolve(conversations)
      }
    }

    request.onerror = () => reject(request.error)
  })
}

/**
 * 대화 삭제
 */
export async function deleteConversation(id) {
  await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.delete(id)

    request.onsuccess = () => resolve(true)
    request.onerror = () => reject(request.error)
  })
}

/**
 * 모든 대화 삭제
 */
export async function clearAllConversations() {
  await initDB()

  return new Promise((resolve, reject) => {
    const transaction = db.transaction([STORE_NAME], 'readwrite')
    const store = transaction.objectStore(STORE_NAME)
    const request = store.clear()

    request.onsuccess = () => resolve(true)
    request.onerror = () => reject(request.error)
  })
}

/**
 * 새 대화 생성
 */
export function createConversation(config) {
  const now = Date.now()
  return {
    id: `conv_${now}_${Math.random().toString(36).substr(2, 9)}`,
    topic: config.topic,
    agentCount: config.agent_count,
    speed: config.speed,
    models: config.models,
    limits: config.limits,      // 안전 설정 (maxTurns, maxCost, maxMinutes)
    file_ids: config.file_ids || [],  // 첨부 파일 ID 목록
    autoStart: config.auto_start !== false,
    messages: [],
    agents: [],
    tokenUsage: {
      totalInput: 0,
      totalOutput: 0,
      history: []
    },
    createdAt: now,
    updatedAt: now,
    status: 'active' // active, paused, stopped
  }
}

/**
 * 대화에 메시지 추가
 */
export async function addMessageToConversation(conversationId, message) {
  const conversation = await getConversation(conversationId)
  if (!conversation) return null

  conversation.messages.push({
    ...message,
    timestamp: Date.now()
  })

  return saveConversation(conversation)
}

/**
 * 대화 토큰 사용량 업데이트
 */
export async function updateTokenUsage(conversationId, usage) {
  const conversation = await getConversation(conversationId)
  if (!conversation) return null

  conversation.tokenUsage = {
    totalInput: usage.totalInput || conversation.tokenUsage.totalInput,
    totalOutput: usage.totalOutput || conversation.tokenUsage.totalOutput,
    history: [...conversation.tokenUsage.history, ...usage.history]
  }

  return saveConversation(conversation)
}

/**
 * 대화 상태 업데이트
 */
export async function updateConversationStatus(conversationId, status) {
  const conversation = await getConversation(conversationId)
  if (!conversation) return null

  conversation.status = status
  return saveConversation(conversation)
}

/**
 * 대화 요약 정보 생성 (목록용)
 */
export function getConversationSummary(conversation) {
  const lastMessage = conversation.messages[conversation.messages.length - 1]
  const messageCount = conversation.messages.length

  return {
    id: conversation.id,
    topic: conversation.topic,
    preview: lastMessage?.content?.substring(0, 100) || '',
    messageCount,
    models: conversation.models,
    tokenUsage: conversation.tokenUsage,
    createdAt: conversation.createdAt,
    updatedAt: conversation.updatedAt,
    status: conversation.status
  }
}

/**
 * 날짜 포맷팅
 */
export function formatDate(timestamp) {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return '방금 전'
  if (diffMins < 60) return `${diffMins}분 전`
  if (diffHours < 24) return `${diffHours}시간 전`
  if (diffDays < 7) return `${diffDays}일 전`

  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  })
}
