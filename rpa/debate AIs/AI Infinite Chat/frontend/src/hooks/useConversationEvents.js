/**
 * useConversationEvents - Event Sourcing 기반 대화 상태 관리 훅
 *
 * 핵심 원칙:
 * - Single Source of Truth: 이벤트 로그가 유일한 진실의 원천
 * - Sequence-Based: 시퀀스 번호로 이벤트 순서 및 누락 관리
 * - Derived State: messages, agents, tokenUsage는 이벤트 로그에서 파생
 *
 * 기존 문제점 해결:
 * - Race Condition: 시퀀스 기반 순서 보장
 * - 메시지 누락: 누락 감지 및 재동기화
 * - 중복 방지: 시퀀스 번호로 확실한 중복 체크
 */

import { useState, useRef, useCallback, useMemo, useEffect } from 'react'

// 이벤트 타입 상수
const EventTypes = {
  CONVERSATION_STARTED: 'conversation_started',
  CONVERSATION_ENDED: 'conversation_ended',
  CONVERSATION_PAUSED: 'paused',
  CONVERSATION_RESUMED: 'resumed',
  CONVERSATION_STOPPED: 'stopped',
  AGENT_START: 'agent_start',
  AGENT_TOKEN: 'token',
  AGENT_COMPLETE: 'agent_complete',
  USER_MESSAGE: 'user_message',
  USER_INTERVENE: 'user_intervention_ack',
  ERROR: 'error',
  LIMIT_REACHED: 'limit_reached',
  SPEED_CHANGED: 'speed_changed',
  RATE_LIMITED: 'rate_limited'
}

// 동기화 요청 디바운스 시간 (ms)
const SYNC_DEBOUNCE_MS = 1000

/**
 * 이벤트 로그 기반 대화 상태 관리 훅
 *
 * @param {Object} options
 * @param {string} options.sessionId - 세션 ID
 * @param {Object} options.initialConversation - 초기 대화 데이터 (복원용)
 * @param {Function} options.onMissedEvents - 이벤트 누락 감지 시 콜백
 * @returns {Object} 대화 상태 및 핸들러
 */
export function useConversationEvents({
  sessionId,
  initialConversation = null,
  onMissedEvents = null
} = {}) {
  // 이벤트 로그 (핵심 상태)
  const [eventLog, setEventLog] = useState([])

  // 마지막으로 처리한 시퀀스 번호
  const lastSeqRef = useRef(0)

  // 스트리밍 상태 (토큰은 이벤트 로그에 저장하지 않음)
  const [currentAgent, setCurrentAgent] = useState(null)
  const [streamingContent, setStreamingContent] = useState('')

  // 대화 상태 플래그
  const [isPaused, setIsPaused] = useState(false)
  const [isStopped, setIsStopped] = useState(false)
  const [isAIRunning, setIsAIRunning] = useState(false)

  // 동기화 관련 상태
  const syncRequestedRef = useRef(false) // 동기화 요청 중인지
  const syncDebounceTimerRef = useRef(null) // 동기화 디바운스 타이머
  const lastSyncRequestSeqRef = useRef(0) // 마지막 동기화 요청 시퀀스

  // 초기화 상태 추적 (재초기화 방지)
  const initializedRef = useRef(false)
  const initializedConversationIdRef = useRef(null) // 초기화된 대화 ID
  const hasReceivedBackendEventsRef = useRef(false) // 백엔드 이벤트 수신 여부

  /**
   * 이벤트 처리 - 시퀀스 기반 중복 방지 및 누락 감지
   */
  const processEvent = useCallback((event) => {
    const seq = event.seq
    const type = event.type

    // DEBUG: 모델별 이벤트 추적
    const agent = event.agent
    const isGemini = agent?.model?.toLowerCase().includes('gemini')
    if (agent) {
      console.log(`[Events DEBUG] ${type} from ${agent.name} (${agent.model}) seq=${seq}`, {
        isGemini,
        hasAgent: !!agent,
        agentId: agent?.id,
        contentLength: event.content?.length
      })
    }

    // 1. 시퀀스가 없는 이벤트 특별 처리
    if (seq === undefined || seq === null) {
      // 토큰 이벤트 - 스트리밍 상태만 업데이트
      if (type === EventTypes.AGENT_TOKEN) {
        setStreamingContent(prev => prev + (event.content || ''))
        return true
      }

      // 사용자 메시지 이벤트 - 로컬에서 생성된 경우 이벤트 로그에 추가/업데이트
      if (type === EventTypes.USER_MESSAGE) {
        setEventLog(prev => {
          // event_id로 기존 이벤트 찾기
          const existingIndex = event.event_id
            ? prev.findIndex(e => e.event_id === event.event_id)
            : -1

          if (existingIndex >= 0) {
            // 기존 이벤트 업데이트 (isPending 상태 변경 등)
            const updated = [...prev]
            updated[existingIndex] = {
              ...updated[existingIndex],
              ...event,
              seq: updated[existingIndex].seq // 기존 seq 유지
            }
            console.log(`[Events] Updated USER_MESSAGE: ${event.event_id}, isPending: ${event.isPending}`)
            return updated
          }

          // 새 이벤트 추가
          // 로컬 시퀀스 번호 할당 (기존 최대값 + 0.5로 중간에 삽입)
          const maxSeq = prev.length > 0 ? Math.max(...prev.map(e => e.seq || 0)) : 0
          const localEvent = {
            ...event,
            seq: maxSeq + 0.5, // 소수점으로 로컬 이벤트 표시
            _isLocal: true
          }
          console.log(`[Events] Added local USER_MESSAGE: ${event.event_id}, isPending: ${event.isPending}`)
          return [...prev, localEvent]
        })
        return true
      }

      return true
    }

    // 백엔드에서 이벤트를 받았음을 표시 (재초기화 방지용)
    hasReceivedBackendEventsRef.current = true

    // 2. 중복 체크 (이미 처리한 시퀀스)
    if (seq <= lastSeqRef.current) {
      console.log(`[Events] Skipping duplicate/old event seq=${seq} (last=${lastSeqRef.current})`)
      return false
    }

    // 3. 누락 감지 (시퀀스가 연속적이지 않음)
    // 단, 아직 동기화 요청 중이면 추가 요청하지 않음
    // 그리고 첫 번째 이벤트(seq=1)이면 갭 체크 안함
    const hasGap = seq > lastSeqRef.current + 1 && lastSeqRef.current > 0
    if (hasGap && !syncRequestedRef.current) {
      const missedCount = seq - lastSeqRef.current - 1
      console.warn(`[Events] Missed ${missedCount} events (expected=${lastSeqRef.current + 1}, got=${seq})`)

      // 디바운스된 동기화 요청 (단, 이미 요청한 시퀀스와 동일하면 무시)
      if (onMissedEvents && !syncDebounceTimerRef.current && lastSyncRequestSeqRef.current !== lastSeqRef.current) {
        syncDebounceTimerRef.current = setTimeout(() => {
          // 아직 동기화 요청 중이 아닐 때만
          if (!syncRequestedRef.current) {
            console.log(`[Events] Requesting sync from seq ${lastSeqRef.current + 1}`)
            syncRequestedRef.current = true
            lastSyncRequestSeqRef.current = lastSeqRef.current
            onMissedEvents({
              expectedSeq: lastSeqRef.current + 1,
              receivedSeq: seq,
              missedCount
            })
          }
          syncDebounceTimerRef.current = null
        }, SYNC_DEBOUNCE_MS)
      }
    }

    // 4. 시퀀스 업데이트 (갭이 있어도 일단 최신으로 업데이트 - 무한 루프 방지)
    lastSeqRef.current = seq

    // 5. 이벤트 로그에 추가 (토큰 제외)
    if (type !== EventTypes.AGENT_TOKEN) {
      setEventLog(prev => {
        // 중복 체크 (이벤트 로그에 이미 있는 seq인지)
        if (prev.some(e => e.seq === seq)) {
          return prev
        }
        return [...prev, event]
      })
    }

    // 6. 이벤트 타입별 상태 업데이트
    switch (type) {
      case EventTypes.CONVERSATION_STARTED:
        setIsAIRunning(true)
        setIsStopped(false)
        setIsPaused(false)
        break

      case EventTypes.AGENT_START:
        console.log('[Events DEBUG] agent_start: Setting currentAgent=', event.agent)
        setCurrentAgent(event.agent)
        setStreamingContent('')
        break

      case EventTypes.AGENT_TOKEN:
        setStreamingContent(prev => prev + (event.content || ''))
        break

      case EventTypes.AGENT_COMPLETE:
        console.log('[Events DEBUG] agent_complete: Clearing currentAgent, content length=', event.content?.length)
        console.log('[Events DEBUG] agent_complete: event.agent=', event.agent)
        setCurrentAgent(null)
        setStreamingContent('')
        break

      case EventTypes.CONVERSATION_PAUSED:
        setIsPaused(true)
        break

      case EventTypes.CONVERSATION_RESUMED:
        setIsPaused(false)
        setIsAIRunning(true)
        break

      case EventTypes.CONVERSATION_STOPPED:
      case EventTypes.CONVERSATION_ENDED:
        setIsStopped(true)
        setIsAIRunning(false)
        setCurrentAgent(null)
        setStreamingContent('')
        break

      case EventTypes.LIMIT_REACHED:
        setIsStopped(true)
        setIsAIRunning(false)
        break

      default:
        break
    }

    console.log(`[Events] Processed event: type=${type}, seq=${seq}`)
    return true
  }, [onMissedEvents])

  /**
   * 여러 이벤트 일괄 처리 (재동기화용)
   */
  const processEvents = useCallback((events) => {
    if (!Array.isArray(events)) return

    console.log(`[Events] Processing batch of ${events.length} events`)

    // 동기화 완료 플래그 설정
    syncRequestedRef.current = false

    // 시퀀스 순서로 정렬
    const sorted = [...events].sort((a, b) => (a.seq || 0) - (b.seq || 0))

    for (const event of sorted) {
      processEvent(event)
    }
  }, [processEvent])

  /**
   * 이벤트 로그 초기화 (새 대화 또는 복원)
   * 주의: 백엔드에서 이벤트를 이미 받은 경우 재초기화하지 않음
   */
  const initializeFromConversation = useCallback((conversation) => {
    if (!conversation) return

    const conversationId = conversation.id

    // 다른 대화로 전환된 경우 - 상태 리셋 후 재초기화
    if (initializedConversationIdRef.current && initializedConversationIdRef.current !== conversationId) {
      console.log(`[Events] Conversation changed: ${initializedConversationIdRef.current} -> ${conversationId}, resetting`)
      // 상태 리셋
      setEventLog([])
      lastSeqRef.current = 0
      syncRequestedRef.current = false
      lastSyncRequestSeqRef.current = 0
      initializedRef.current = false
      hasReceivedBackendEventsRef.current = false
      if (syncDebounceTimerRef.current) {
        clearTimeout(syncDebounceTimerRef.current)
        syncDebounceTimerRef.current = null
      }
      setCurrentAgent(null)
      setStreamingContent('')
      setIsPaused(false)
      setIsStopped(false)
      setIsAIRunning(false)
    }

    // 이미 백엔드에서 이벤트를 받았으면 재초기화 하지 않음 (무한 루프 방지)
    if (hasReceivedBackendEventsRef.current) {
      console.log('[Events] Skipping re-initialization: already receiving backend events')
      return
    }

    // 이미 같은 대화로 초기화되었으면 스킵
    if (initializedRef.current && initializedConversationIdRef.current === conversationId) {
      console.log('[Events] Skipping re-initialization: already initialized with same conversation')
      return
    }

    // 기존 메시지를 이벤트 로그 형태로 변환
    const events = []
    let seq = 0

    // 에이전트 정보가 있으면 conversation_started 이벤트 추가
    if (conversation.agents?.length > 0) {
      events.push({
        seq: ++seq,
        type: EventTypes.CONVERSATION_STARTED,
        data: { agents: conversation.agents },
        timestamp: conversation.createdAt || Date.now()
      })
    }

    // 메시지를 이벤트로 변환
    if (conversation.messages) {
      for (const msg of conversation.messages) {
        if (msg.isUser || msg.isInitialTopic) {
          events.push({
            seq: ++seq,
            type: EventTypes.USER_MESSAGE,
            event_id: msg.id,
            content: msg.content,
            isInitialTopic: msg.isInitialTopic || false,
            hasFiles: msg.hasFiles || false,
            timestamp: msg.timestamp || Date.now()
          })
        } else if (msg.agent) {
          events.push({
            seq: ++seq,
            type: EventTypes.AGENT_COMPLETE,
            event_id: msg.id,
            agent: msg.agent,
            content: msg.content,
            usage: msg.usage,
            interrupted: msg.interrupted || false,
            timestamp: msg.timestamp || Date.now()
          })
        } else if (msg.isError) {
          events.push({
            seq: ++seq,
            type: EventTypes.ERROR,
            event_id: msg.id,
            error: msg.content,
            recoverable: msg.recoverable || false,
            timestamp: msg.timestamp || Date.now()
          })
        }
      }
    }

    // 상태 복원
    setEventLog(events)
    lastSeqRef.current = seq
    initializedRef.current = true
    initializedConversationIdRef.current = conversationId

    // 대화 상태 복원
    if (conversation.status === 'stopped') {
      setIsStopped(true)
      setIsAIRunning(false)
    } else if (conversation.status === 'paused') {
      setIsPaused(true)
    }

    console.log(`[Events] Initialized from conversation: ${events.length} events, lastSeq=${seq}`)
  }, []) // 의존성 없음 - ref로 중복 방지

  /**
   * 이벤트 로그 리셋
   */
  const reset = useCallback(() => {
    setEventLog([])
    lastSeqRef.current = 0
    syncRequestedRef.current = false
    lastSyncRequestSeqRef.current = 0
    initializedRef.current = false
    initializedConversationIdRef.current = null
    hasReceivedBackendEventsRef.current = false
    if (syncDebounceTimerRef.current) {
      clearTimeout(syncDebounceTimerRef.current)
      syncDebounceTimerRef.current = null
    }
    setCurrentAgent(null)
    setStreamingContent('')
    setIsPaused(false)
    setIsStopped(false)
    setIsAIRunning(false)
    console.log('[Events] Reset')
  }, [])

  // =====================================================
  // 파생 상태 (이벤트 로그에서 계산)
  // =====================================================

  /**
   * 메시지 목록 (agent_complete + user_message 이벤트에서 파생)
   */
  const messages = useMemo(() => {
    const result = []

    for (const event of eventLog) {
      if (event.type === EventTypes.AGENT_COMPLETE) {
        const msg = {
          id: event.event_id || event._msgId || `msg_${event.seq}`,
          seq: event.seq,
          agent: event.agent,
          content: event.content || '',
          timestamp: event.timestamp,
          usage: event.usage,
          interrupted: event.interrupted || false
        }
        // DEBUG: 메시지 파생 로깅
        const isGemini = event.agent?.model?.toLowerCase().includes('gemini')
        console.log(`[Events DEBUG] Deriving message from agent_complete: ${event.agent?.name} (${event.agent?.model})`, {
          isGemini,
          hasAgent: !!msg.agent,
          contentLength: msg.content?.length
        })
        result.push(msg)
      } else if (event.type === EventTypes.USER_MESSAGE) {
        result.push({
          id: event.event_id || `user_${event.seq}`,
          seq: event.seq,
          isUser: true,
          content: event.content || '',
          timestamp: event.timestamp,
          isInitialTopic: event.isInitialTopic || false,
          hasFiles: event.hasFiles || false,
          isPending: event.isPending || false
        })
      } else if (event.type === EventTypes.ERROR) {
        result.push({
          id: event.event_id || `error_${event.seq}`,
          seq: event.seq,
          isError: true,
          content: event.error || '',
          timestamp: event.timestamp,
          recoverable: event.recoverable || false
        })
      }
    }

    return result
  }, [eventLog])

  /**
   * 에이전트 목록 (conversation_started 이벤트에서 파생)
   */
  const agents = useMemo(() => {
    for (const event of eventLog) {
      if (event.type === EventTypes.CONVERSATION_STARTED) {
        return event.data?.agents || []
      }
    }
    return []
  }, [eventLog])

  /**
   * 토큰 사용량 (agent_complete 이벤트에서 파생)
   */
  const tokenUsage = useMemo(() => {
    let totalInput = 0
    let totalOutput = 0
    const history = []

    for (const event of eventLog) {
      if (event.type === EventTypes.AGENT_COMPLETE && event.usage) {
        totalInput += event.usage.input_tokens || 0
        totalOutput += event.usage.output_tokens || 0
        history.push({
          model: event.agent?.model,
          inputTokens: event.usage.input_tokens || 0,
          outputTokens: event.usage.output_tokens || 0
        })
      }
    }

    return {
      totalInput,
      totalOutput,
      history
    }
  }, [eventLog])

  /**
   * 턴 수 (agent_complete 이벤트 수)
   */
  const turnCount = useMemo(() => {
    return eventLog.filter(e => e.type === EventTypes.AGENT_COMPLETE).length
  }, [eventLog])

  /**
   * 현재 시퀀스 번호
   */
  const currentSeq = lastSeqRef.current

  // 초기 대화 데이터 복원
  useEffect(() => {
    if (initialConversation) {
      initializeFromConversation(initialConversation)
    }
  }, [initialConversation, initializeFromConversation])

  // 정리
  useEffect(() => {
    return () => {
      if (syncDebounceTimerRef.current) {
        clearTimeout(syncDebounceTimerRef.current)
      }
    }
  }, [])

  return {
    // 이벤트 처리
    processEvent,
    processEvents,
    reset,
    initializeFromConversation,

    // 핵심 상태
    eventLog,
    currentSeq,

    // 파생 상태
    messages,
    agents,
    tokenUsage,
    turnCount,

    // 스트리밍 상태
    currentAgent,
    streamingContent,
    setStreamingContent,

    // 대화 상태 플래그
    isPaused,
    setIsPaused,
    isStopped,
    setIsStopped,
    isAIRunning,
    setIsAIRunning,

    // 유틸리티
    EventTypes
  }
}

export { EventTypes }
export default useConversationEvents
