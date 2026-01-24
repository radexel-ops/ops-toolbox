/**
 * Debug Logger for AI Infinite Chat
 *
 * 디버깅용 상세 로그 유틸리티
 * 서비스 안정화 후 삭제 예정
 */

// 로그 저장소
const logHistory = []
const MAX_LOG_HISTORY = 500

// 로그 레벨
const LOG_LEVELS = {
  ACTION: 'ACTION',      // 사용자 액션 (버튼 클릭, 입력 등)
  WS_SEND: 'WS_SEND',    // WebSocket 전송
  WS_RECV: 'WS_RECV',    // WebSocket 수신
  STATE: 'STATE',        // 상태 변화
  AGENT: 'AGENT',        // 에이전트 관련
  ERROR: 'ERROR',        // 에러
  SYSTEM: 'SYSTEM',      // 시스템 이벤트
}

// 색상 매핑 (콘솔 출력용)
const LEVEL_COLORS = {
  ACTION: '#4CAF50',     // 초록
  WS_SEND: '#2196F3',    // 파랑
  WS_RECV: '#9C27B0',    // 보라
  STATE: '#FF9800',      // 주황
  AGENT: '#00BCD4',      // 청록
  ERROR: '#F44336',      // 빨강
  SYSTEM: '#607D8B',     // 회색
}

// 타임스탬프 포맷
const formatTime = () => {
  const now = new Date()
  return now.toISOString().substr(11, 12) // HH:MM:SS.mmm
}

// 로그 항목 생성
const createLogEntry = (level, category, message, data = null) => {
  const entry = {
    timestamp: formatTime(),
    fullTimestamp: new Date().toISOString(),
    level,
    category,
    message,
    data: data ? JSON.parse(JSON.stringify(data)) : null, // Deep copy
  }

  // 히스토리에 저장
  logHistory.push(entry)
  if (logHistory.length > MAX_LOG_HISTORY) {
    logHistory.shift()
  }

  return entry
}

// 콘솔에 출력
const printToConsole = (entry) => {
  const color = LEVEL_COLORS[entry.level] || '#000'
  const prefix = `[${entry.timestamp}] [${entry.level}] [${entry.category}]`

  if (entry.data) {
    console.log(
      `%c${prefix} ${entry.message}`,
      `color: ${color}; font-weight: bold;`,
      entry.data
    )
  } else {
    console.log(
      `%c${prefix} ${entry.message}`,
      `color: ${color}; font-weight: bold;`
    )
  }
}

// === 메인 로깅 함수들 ===

/**
 * 사용자 액션 로그
 * @param {string} action - 액션 이름 (예: 'CLICK_START', 'CLICK_STOP')
 * @param {object} details - 상세 정보
 */
export const logAction = (action, details = null) => {
  const entry = createLogEntry(LOG_LEVELS.ACTION, 'USER', action, details)
  printToConsole(entry)
}

/**
 * WebSocket 전송 로그
 * @param {string} messageType - 메시지 타입
 * @param {object} payload - 전송 데이터
 */
export const logWsSend = (messageType, payload = null) => {
  // 민감한 데이터 필터링
  const filteredPayload = payload ? {
    ...payload,
    existing_messages: payload.existing_messages ? `[${payload.existing_messages.length} messages]` : undefined,
    existing_agents: payload.existing_agents ? `[${payload.existing_agents.length} agents]` : undefined,
  } : null

  const entry = createLogEntry(LOG_LEVELS.WS_SEND, 'WEBSOCKET', `SEND: ${messageType}`, filteredPayload)
  printToConsole(entry)
}

/**
 * WebSocket 수신 로그
 * @param {string} messageType - 메시지 타입
 * @param {object} payload - 수신 데이터
 */
export const logWsRecv = (messageType, payload = null) => {
  // token 메시지는 내용 축약
  let filteredPayload = payload
  if (messageType === 'token' && payload) {
    filteredPayload = { content: payload.content?.substring(0, 50) + '...' }
  }

  const entry = createLogEntry(LOG_LEVELS.WS_RECV, 'WEBSOCKET', `RECV: ${messageType}`, filteredPayload)
  printToConsole(entry)
}

/**
 * 상태 변화 로그
 * @param {string} stateName - 상태 이름
 * @param {any} oldValue - 이전 값
 * @param {any} newValue - 새 값
 * @param {string} reason - 변경 이유 (선택)
 */
export const logStateChange = (stateName, oldValue, newValue, reason = '') => {
  const entry = createLogEntry(LOG_LEVELS.STATE, 'STATE', `${stateName}: ${oldValue} -> ${newValue}`, {
    state: stateName,
    from: oldValue,
    to: newValue,
    reason: reason || undefined,
  })
  printToConsole(entry)
}

/**
 * 에이전트 관련 로그
 * @param {string} event - 이벤트 (예: 'START', 'COMPLETE', 'CHANGE')
 * @param {object} agentInfo - 에이전트 정보
 */
export const logAgent = (event, agentInfo = null) => {
  const entry = createLogEntry(LOG_LEVELS.AGENT, 'AGENT', event, agentInfo)
  printToConsole(entry)
}

/**
 * 에러 로그
 * @param {string} errorType - 에러 유형
 * @param {string} message - 에러 메시지
 * @param {object} context - 추가 컨텍스트
 */
export const logError = (errorType, message, context = null) => {
  const entry = createLogEntry(LOG_LEVELS.ERROR, 'ERROR', `${errorType}: ${message}`, context)
  printToConsole(entry)
  console.error(`[DEBUG ERROR] ${errorType}:`, message, context)
}

/**
 * 시스템 이벤트 로그
 * @param {string} event - 이벤트 이름
 * @param {object} details - 상세 정보
 */
export const logSystem = (event, details = null) => {
  const entry = createLogEntry(LOG_LEVELS.SYSTEM, 'SYSTEM', event, details)
  printToConsole(entry)
}

// === 유틸리티 함수 ===

/**
 * 전체 로그 히스토리 반환
 */
export const getLogHistory = () => [...logHistory]

/**
 * 로그 히스토리를 JSON 문자열로 내보내기
 */
export const exportLogs = () => {
  return JSON.stringify(logHistory, null, 2)
}

/**
 * 로그 히스토리를 파일로 다운로드
 */
export const downloadLogs = () => {
  const content = exportLogs()
  const blob = new Blob([content], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `debug-logs-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * 로그 히스토리 초기화
 */
export const clearLogs = () => {
  logHistory.length = 0
  console.log('%c[DEBUG] Log history cleared', 'color: #607D8B; font-weight: bold;')
}

/**
 * 특정 레벨의 로그만 필터링
 * @param {string} level - 로그 레벨
 */
export const filterLogs = (level) => {
  return logHistory.filter(entry => entry.level === level)
}

// 전역에서 접근 가능하도록 window에 노출 (디버깅용)
if (typeof window !== 'undefined') {
  window.debugLogger = {
    getLogHistory,
    exportLogs,
    downloadLogs,
    clearLogs,
    filterLogs,
    LOG_LEVELS,
  }
  console.log('%c[DEBUG] Debug logger initialized. Access via window.debugLogger', 'color: #607D8B; font-weight: bold;')
}

export default {
  logAction,
  logWsSend,
  logWsRecv,
  logStateChange,
  logAgent,
  logError,
  logSystem,
  getLogHistory,
  exportLogs,
  downloadLogs,
  clearLogs,
  filterLogs,
  LOG_LEVELS,
}
