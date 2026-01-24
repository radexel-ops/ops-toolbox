import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import useWebSocket from '../hooks/useWebSocket'
import { useConversationEvents, EventTypes } from '../hooks/useConversationEvents'
import AgentMessage from './AgentMessage'
import ConversationControls from './ConversationControls'
import UserInterventionBar from './UserInterventionBar'
import { saveConversation, getConversation } from '../services/storage'
import {
  WS_URL,
  getUserFriendlyError,
  MODEL_PRICING,
  AVAILABLE_MODELS,
  formatCost,
  formatKRW,
  formatTokens,
  SAFETY_LIMITS
} from '../config'
// 디버그 로거 (서비스 안정화 후 삭제 예정)
import {
  logAction,
  logWsSend,
  logWsRecv,
  logStateChange,
  logAgent,
  logError,
  logSystem
} from '../utils/debugLogger'

// SVG Icons
const Icons = {
  Refresh: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  ),
  Users: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),
  DollarSign: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="1" x2="12" y2="23" />
      <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  ),
  ChevronDown: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  ),
  Close: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
  Wifi: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M5 12.55a11 11 0 0 1 14.08 0" />
      <path d="M1.42 9a16 16 0 0 1 21.16 0" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <line x1="12" y1="20" x2="12.01" y2="20" />
    </svg>
  ),
  WifiOff: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="1" y1="1" x2="23" y2="23" />
      <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
      <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
      <path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
      <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
      <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
      <line x1="12" y1="20" x2="12.01" y2="20" />
    </svg>
  ),
  AlertTriangle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  Clock: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  Shield: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  )
}

/**
 * ConversationView - AI 대화 뷰 컴포넌트
 *
 * @param {Object} props
 * @param {Object} props.conversation - 대화 데이터
 * @param {Object} props.config - 대화 설정 (topic, models, limits 등)
 * @param {string} props.mode - 'new' (새 대화 시작, AI 자동 시작) | 'view' (기존 대화 보기, AI 자동 시작 안 함)
 * @param {Function} props.onUpdate - 대화 업데이트 콜백
 * @param {Function} props.onEnd - 대화 종료 콜백
 */
function ConversationView({ conversation, config, mode, onUpdate, onEnd }) {
  // mode 검증: 'new' 또는 'view'만 허용
  const isNewConversation = mode === 'new'
  const isViewMode = mode === 'view'

  // 세션 ID
  const sessionId = useRef(conversation?.id || `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`)

  // =====================================================
  // Event Sourcing 기반 상태 관리 훅
  // =====================================================
  const {
    processEvent,
    processEvents,
    reset: resetEventLog,
    initializeFromConversation,

    // 파생 상태 (이벤트 로그에서 계산)
    messages,
    agents,
    tokenUsage,
    turnCount,
    currentSeq,

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
    setIsAIRunning
  } = useConversationEvents({
    sessionId: sessionId.current,
    initialConversation: conversation,
    onMissedEvents: ({ expectedSeq, receivedSeq, missedCount }) => {
      // 이벤트 누락 감지 시 재동기화 요청
      console.warn(`[ConvView] Missed ${missedCount} events, requesting sync from seq ${expectedSeq}`)
      sendMessage({
        type: 'sync_events',
        session_id: sessionId.current,
        since_seq: expectedSeq
      })
    }
  })

  // view 모드에서 AI가 대기 중인지 (사용자 입력 대기)
  const [isWaitingForUser, setIsWaitingForUser] = useState(isViewMode)
  const [speed, setSpeed] = useState(config?.speed || 'normal')
  const [showScrollButton, setShowScrollButton] = useState(false)
  const [showCostDetail, setShowCostDetail] = useState(false)

  // Safety limits state
  const limits = config?.limits || SAFETY_LIMITS
  const [elapsedMinutes, setElapsedMinutes] = useState(0)
  const [warning, setWarning] = useState(null) // { type: 'turns'|'cost'|'time', message, level: 'warning'|'danger' }
  const [isTabActive, setIsTabActive] = useState(true)
  const [autoPausedReason, setAutoPausedReason] = useState(null) // null | 'inactive' | 'limit_reached'
  const startTimeRef = useRef(Date.now())

  const messagesEndRef = useRef(null)
  const messagesAreaRef = useRef(null)
  const conversationStarted = useRef(false)
  const isNearBottom = useRef(true)
  const onUpdateRef = useRef(onUpdate) // onUpdate의 최신 참조 유지
  const pendingUserMessageRef = useRef(null) // AI 응답 중 대기하는 사용자 메시지

  // onUpdate ref 업데이트
  useEffect(() => {
    onUpdateRef.current = onUpdate
  }, [onUpdate])

  // 직접 IndexedDB에 저장하는 헬퍼
  const saveToStorageRef = useRef(null) // 가장 최근 저장 Promise 추적
  const conversationBaseRef = useRef(conversation) // 초기 대화 데이터 캐시

  const saveToStorage = useCallback(async (updates = {}) => {
    const convId = sessionId.current
    if (!convId) return

    try {
      // 전체 대화 객체를 직접 구성
      const fullConversation = {
        ...conversationBaseRef.current,
        id: convId,
        messages: updates.messages || messages,
        tokenUsage: updates.tokenUsage || tokenUsage,
        agents: updates.agents || agents,
        status: updates.status || (isStopped ? 'stopped' : 'active'),
        updatedAt: Date.now()
      }

      // 이전 저장이 완료될 때까지 대기 (순차 저장 보장)
      if (saveToStorageRef.current) {
        await saveToStorageRef.current.catch(() => {}) // 이전 에러 무시
      }

      // 새 저장 시작
      const savePromise = saveConversation(fullConversation)
      saveToStorageRef.current = savePromise

      await savePromise
      console.log('[ConvView] Saved to IndexedDB:', convId, 'messages:', fullConversation.messages.length)

      // 부모 컴포넌트에도 알림
      if (onUpdateRef.current) {
        onUpdateRef.current(updates)
      }
    } catch (err) {
      console.error('[ConvView] Failed to save to IndexedDB:', err)
    }
  }, [messages, tokenUsage, agents, isStopped])

  // 컴포넌트 마운트 시 로그
  useEffect(() => {
    console.log('[ConvView] Component mounted:', {
      conversationId: conversation?.id,
      mode: mode,
      messageCount: conversation?.messages?.length || 0,
      status: conversation?.status
    })
  }, [])

  // 컴포넌트 언마운트 시 최종 상태 저장
  useEffect(() => {
    return () => {
      const convId = sessionId.current
      if (convId && messages.length > 0) {
        console.log('[ConvView] Component unmounting, saving final state')
        saveToStorage()
      }
    }
  }, [messages, saveToStorage])

  // Calculate real-time cost using actual token data
  const estimatedCost = useMemo(() => {
    if (tokenUsage.totalInput > 0 || tokenUsage.totalOutput > 0) {
      let totalCost = 0

      tokenUsage.history.forEach(usage => {
        const pricing = MODEL_PRICING[usage.model]
        if (pricing) {
          const inputCost = (usage.inputTokens * pricing.input) / 1_000_000
          const outputCost = (usage.outputTokens * pricing.output) / 1_000_000
          totalCost += inputCost + outputCost
        }
      })

      if (tokenUsage.history.length === 0 && config?.models?.length > 0) {
        const avgPricing = config.models.reduce((sum, m) => {
          const p = MODEL_PRICING[m.id]
          return p ? { input: sum.input + p.input, output: sum.output + p.output, count: sum.count + 1 }
            : sum
        }, { input: 0, output: 0, count: 0 })

        if (avgPricing.count > 0) {
          const avgInput = avgPricing.input / avgPricing.count
          const avgOutput = avgPricing.output / avgPricing.count
          totalCost = (tokenUsage.totalInput * avgInput + tokenUsage.totalOutput * avgOutput) / 1_000_000
        }
      }

      return totalCost
    }

    if (!config?.models || config.models.length === 0 || turnCount === 0) return 0

    let totalCost = 0
    const msgsPerModel = turnCount / config.models.length

    config.models.forEach(model => {
      const pricing = MODEL_PRICING[model.id]
      if (pricing) {
        const avgTokens = pricing.avgTokensPerMsg
        const costPerMsg = ((pricing.input + pricing.output) / 2 * avgTokens) / 1_000_000
        totalCost += costPerMsg * msgsPerModel
      }
    })

    return totalCost
  }, [turnCount, config?.models, tokenUsage])

  const { isConnected, connectionState, sendMessage, lastMessage, reconnect } = useWebSocket(WS_URL)

  // Start or resume conversation (mode에 따라 동작 분리)
  useEffect(() => {
    if (!isConnected || !config || conversationStarted.current) return

    conversationStarted.current = true

    // VIEW 모드: 기존 대화 보기 - AI 자동 시작 안 함
    if (isViewMode) {
      console.log('[ConvView] VIEW mode - displaying existing conversation')
      return
    }

    // NEW 모드: 새 대화 시작 - WebSocket으로 start_conversation 전송
    if (isNewConversation) {
      console.log('[ConvView] NEW mode - starting new conversation')

      // 초기 토픽을 사용자 메시지로 추가 (대화창에 표시)
      if (config.topic) {
        const initialTopicEvent = {
          type: EventTypes.USER_MESSAGE,
          event_id: `topic_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          content: config.topic,
          isInitialTopic: true,
          hasFiles: (config.file_ids?.length || 0) > 0,
          timestamp: Date.now()
        }
        processEvent(initialTopicEvent)
        console.log('[ConvView] Added initial topic as user message')
      }

      sendMessage({
        type: 'start_conversation',
        session_id: sessionId.current,
        topic: config.topic,
        agent_count: config.agentCount || config.agent_count,
        speed: config.speed,
        auto_start: true,
        models: config.models,
        limits: config.limits,
        file_ids: config.file_ids || []
      })
    }
  }, [isConnected, config, sendMessage, isViewMode, isNewConversation, processEvent])

  // 이미 처리된 메시지 ID 추적 (토큰 중복 방지)
  const processedMsgIdsRef = useRef(new Set())

  // =====================================================
  // Event Sourcing 기반 WebSocket 메시지 처리
  // =====================================================
  useEffect(() => {
    if (!lastMessage) return

    const data = lastMessage

    // 메시지 ID로 중복 처리 방지 (특히 토큰)
    const msgId = data._msgId
    if (msgId && processedMsgIdsRef.current.has(msgId)) {
      return // 이미 처리된 메시지
    }
    if (msgId) {
      processedMsgIdsRef.current.add(msgId)
      // 메모리 누수 방지: 오래된 ID 정리 (최근 1000개만 유지)
      if (processedMsgIdsRef.current.size > 1000) {
        const ids = Array.from(processedMsgIdsRef.current)
        processedMsgIdsRef.current = new Set(ids.slice(-500))
      }
    }

    // 디버그 로그
    logWsRecv(data.type, data)

    // DEBUG: 모델별 이벤트 추적
    if (data.agent) {
      const isGemini = data.agent.model?.toLowerCase().includes('gemini')
      console.log(`[ConvView DEBUG] Received ${data.type} from ${data.agent.name} (${data.agent.model})`, {
        isGemini,
        seq: data.seq,
        contentLength: data.content?.length
      })
    }

    // 동기화 응답 처리 (여러 이벤트 일괄 처리)
    if (data.type === 'sync_events' && Array.isArray(data.events)) {
      console.log('[ConvView] Processing sync_events:', data.events.length)
      processEvents(data.events)
      return
    }

    // 모든 이벤트를 훅의 processEvent로 전달
    // 훅이 시퀀스 기반 중복 방지, 상태 업데이트 등을 처리
    const processed = processEvent(data)
    console.log(`[ConvView DEBUG] processEvent returned:`, processed)

    // 특수 이벤트 후처리
    switch (data.type) {
      case 'conversation_started':
        // 에이전트 정보를 base ref에 업데이트 (저장용)
        conversationBaseRef.current = {
          ...conversationBaseRef.current,
          agents: data.data?.agents || []
        }
        // 저장
        saveToStorage({ agents: data.data?.agents })
        break

      case 'agent_complete':
        // DEBUG: agent_complete 처리 확인
        console.log('[ConvView DEBUG] agent_complete processed, current messages count:', messages.length)
        // 메시지 저장
        saveToStorage()

        // 대기 중인 사용자 메시지가 있으면 전송
        if (pendingUserMessageRef.current) {
          const pending = pendingUserMessageRef.current
          console.log('[ConvView] Sending pending user message after agent_complete')

          // 이벤트 로그에서 pending 플래그 제거 (새 이벤트로 업데이트)
          processEvent({
            type: EventTypes.USER_MESSAGE,
            event_id: pending.eventId,
            content: pending.content,
            hasFiles: pending.fileIds?.length > 0,
            isPending: false, // 대기 상태 해제
            timestamp: Date.now()
          })

          // 백엔드에 전송
          sendMessage({
            type: 'user_intervene',
            session_id: sessionId.current,
            content: pending.content,
            file_ids: pending.fileIds || []
          })

          // 대기 메시지 초기화
          pendingUserMessageRef.current = null
        }
        break

      case 'stopped':
      case 'conversation_ended':
        // 스트리밍 중인 내용이 있으면 저장 (agent_complete 누락 대비)
        if (currentAgent && streamingContent) {
          console.log('[ConvView] Saving streaming content on stop/end')
          // 훅에서 이미 처리됨 - 저장만 수행
        }
        saveToStorage({ status: 'stopped' })
        if (onUpdate) onUpdate({ status: 'stopped' })
        break

      case 'limit_reached':
        setAutoPausedReason('limit_reached')
        setWarning({
          type: data.limit_type,
          message: data.message,
          level: 'danger'
        })
        if (onUpdate) onUpdate({ status: 'stopped' })
        break

      case 'paused':
        if (onUpdate) onUpdate({ status: 'paused' })
        break

      case 'resumed':
        if (onUpdate) onUpdate({ status: 'active' })
        break

      case 'speed_changed':
        setSpeed(data.speed)
        break

      case 'error':
        // 에러 로그
        const errorContent = getUserFriendlyError(data.content || data.error)
        logError('API_ERROR', errorContent, { recoverable: data.recoverable })
        break
    }
  }, [lastMessage, processEvent, processEvents, onUpdate, saveToStorage, currentAgent, streamingContent])

  // Scroll position detection
  const checkIfNearBottom = useCallback(() => {
    const container = messagesAreaRef.current
    if (!container) return true

    const threshold = 150
    const scrollBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    return scrollBottom < threshold
  }, [])

  const handleScroll = useCallback(() => {
    const nearBottom = checkIfNearBottom()
    isNearBottom.current = nearBottom
    setShowScrollButton(!nearBottom)
  }, [checkIfNearBottom])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    isNearBottom.current = true
    setShowScrollButton(false)
  }, [])

  useEffect(() => {
    const container = messagesAreaRef.current
    if (!container) return

    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => container.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  useEffect(() => {
    if (isNearBottom.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, streamingContent])

  // Timer for elapsed time tracking
  useEffect(() => {
    if (isStopped) return

    const timer = setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTimeRef.current) / 60000)
      setElapsedMinutes(elapsed)
    }, 10000) // Update every 10 seconds

    return () => clearInterval(timer)
  }, [isStopped])

  // Tab visibility detection for auto-pause
  useEffect(() => {
    if (!limits.pauseOnInactive) return

    const handleVisibilityChange = () => {
      const isVisible = document.visibilityState === 'visible'
      setIsTabActive(isVisible)

      if (!isVisible && !isPaused && !isStopped) {
        // Tab became inactive - pause after timeout
        const timeout = setTimeout(() => {
          if (document.visibilityState !== 'visible' && !isPaused && !isStopped) {
            setAutoPausedReason('inactive')
            handlePause()
          }
        }, (limits.inactiveTimeout || SAFETY_LIMITS.inactiveTimeout) * 1000)

        return () => clearTimeout(timeout)
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange)
  }, [limits.pauseOnInactive, limits.inactiveTimeout, isPaused, isStopped])

  // Safety limit checking
  useEffect(() => {
    if (isStopped) return

    const warningThreshold = SAFETY_LIMITS.warningThreshold / 100

    // Check turn limit
    const maxTurns = limits.maxTurns || SAFETY_LIMITS.maxTurns
    if (turnCount >= maxTurns) {
      setAutoPausedReason('limit_reached')
      handleStop()
      setWarning({
        type: 'turns',
        message: `최대 턴 수(${maxTurns}회)에 도달하여 대화가 자동 종료되었습니다.`,
        level: 'danger'
      })
      return
    } else if (turnCount >= maxTurns * warningThreshold && !warning) {
      setWarning({
        type: 'turns',
        message: `턴 수가 ${turnCount}/${maxTurns}회에 도달했습니다. 곧 자동 종료됩니다.`,
        level: 'warning'
      })
    }

    // Check cost limit
    const maxCost = limits.maxCost || SAFETY_LIMITS.maxCost
    if (estimatedCost >= maxCost) {
      setAutoPausedReason('limit_reached')
      handleStop()
      setWarning({
        type: 'cost',
        message: `최대 비용($${maxCost.toFixed(2)})에 도달하여 대화가 자동 종료되었습니다.`,
        level: 'danger'
      })
      return
    } else if (estimatedCost >= maxCost * warningThreshold && (!warning || warning.type !== 'cost')) {
      setWarning({
        type: 'cost',
        message: `비용이 ${formatCost(estimatedCost)}/$${maxCost.toFixed(2)}에 도달했습니다. 곧 자동 종료됩니다.`,
        level: 'warning'
      })
    }

    // Check time limit
    const maxMinutes = limits.maxMinutes || SAFETY_LIMITS.maxMinutes
    if (elapsedMinutes >= maxMinutes) {
      setAutoPausedReason('limit_reached')
      handleStop()
      setWarning({
        type: 'time',
        message: `최대 시간(${maxMinutes}분)에 도달하여 대화가 자동 종료되었습니다.`,
        level: 'danger'
      })
      return
    } else if (elapsedMinutes >= maxMinutes * warningThreshold && (!warning || warning.type !== 'time')) {
      setWarning({
        type: 'time',
        message: `대화 시간이 ${elapsedMinutes}/${maxMinutes}분에 도달했습니다. 곧 자동 종료됩니다.`,
        level: 'warning'
      })
    }
  }, [turnCount, estimatedCost, elapsedMinutes, limits, isStopped])

  // Control handlers
  const handlePause = useCallback(() => {
    logAction('CLICK_PAUSE', {
      sessionId: sessionId.current,
      currentAgent: currentAgent?.name,
      isAIRunning,
      messageCount: messages.length
    })
    logWsSend('pause', { session_id: sessionId.current })
    setIsPaused(true)
    sendMessage({ type: 'pause', session_id: sessionId.current })
  }, [sendMessage, currentAgent, isAIRunning, messages.length])

  const handleResume = useCallback(() => {
    logAction('CLICK_RESUME', {
      sessionId: sessionId.current,
      wasPaused: isPaused,
      wasWarning: warning?.type,
      messageCount: messages.length
    })
    logWsSend('resume', { session_id: sessionId.current })
    setIsPaused(false)
    setAutoPausedReason(null)
    if (warning?.level === 'warning') {
      setWarning(null) // Clear warning on manual resume
    }
    sendMessage({ type: 'resume', session_id: sessionId.current })
  }, [sendMessage, warning, isPaused, messages.length])

  const handleStop = useCallback(() => {
    logAction('CLICK_STOP', { sessionId: sessionId.current })
    logWsSend('stop', { session_id: sessionId.current })
    // 상태 업데이트
    setIsStopped(true)
    setIsAIRunning(false)
    sendMessage({ type: 'stop', session_id: sessionId.current })
  }, [sendMessage, setIsStopped, setIsAIRunning])

  const handleSpeedChange = useCallback((newSpeed) => {
    setSpeed(newSpeed)
    sendMessage({ type: 'set_speed', session_id: sessionId.current, speed: newSpeed })
  }, [sendMessage])

  const handleUserIntervene = useCallback((message, fileIds = []) => {
    if (message.trim() || fileIds.length > 0) {
      logAction('USER_SEND_MESSAGE', { messageLength: message?.length, hasFiles: fileIds.length > 0 })

      // 사용자 메시지 이벤트 생성
      const userMessageEvent = {
        type: EventTypes.USER_MESSAGE,
        event_id: `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        content: message || (fileIds.length > 0 ? '[파일 첨부]' : ''),
        hasFiles: fileIds.length > 0,
        timestamp: Date.now()
      }

      // 조건을 먼저 저장 (상태 변경 전에)
      const shouldResumeConversation = isStopped || isWaitingForUser

      // 종료된 대화 또는 view 모드에서 대화 재개
      if (shouldResumeConversation) {
        // WebSocket 연결 확인
        if (!isConnected) {
          setWarning({
            type: 'connection',
            message: '서버에 연결되지 않았습니다. 잠시 후 다시 시도해주세요.',
            level: 'warning'
          })
          return
        }

        console.log('[ConvView] Resuming conversation with user message')

        // 상태 업데이트
        setIsStopped(false)
        setIsWaitingForUser(false)
        setAutoPausedReason(null)
        setWarning(null)
        setIsAIRunning(true)

        // 이벤트로 메시지 추가
        processEvent(userMessageEvent)
        saveToStorage({ status: 'active' })

        // 백엔드에 대화 재개 요청
        const defaultModels = [
          { id: 'gpt-5-mini', provider: 'openai' },
          { id: 'gemini-3-flash-preview', provider: 'google' }
        ]
        const defaultLimits = {
          maxTurns: 100,
          maxCost: 1.0,
          maxMinutes: 30,
          pauseOnInactive: true
        }

        const resumePayload = {
          type: 'resume_conversation',
          session_id: sessionId.current,
          topic: config?.topic || '자유 주제',
          agent_count: agents.length || config?.agentCount || config?.agent_count || 2,
          speed: config?.speed || speed || 'normal',
          models: config?.models || defaultModels,
          limits: config?.limits || defaultLimits,
          existing_messages: messages,
          existing_agents: agents,
          user_message: message,
          file_ids: fileIds
        }

        logWsSend('resume_conversation', { session_id: sessionId.current })

        const sent = sendMessage(resumePayload)

        if (!sent) {
          // 전송 실패 시 상태 복구
          setIsStopped(true)
          setIsAIRunning(false)
          setWarning({
            type: 'connection',
            message: '메시지 전송에 실패했습니다. 다시 시도해주세요.',
            level: 'warning'
          })
        }
        return
      }

      // AI가 현재 응답 중인지 확인
      const isAIStreaming = currentAgent !== null

      if (isAIStreaming) {
        // AI가 응답 중이면 메시지를 "대기 중" 상태로 추가
        console.log('[ConvView] AI is streaming, adding pending message')
        const pendingEvent = {
          ...userMessageEvent,
          isPending: true
        }
        processEvent(pendingEvent)
        saveToStorage()

        // 대기 메시지 저장 (agent_complete 후 전송)
        pendingUserMessageRef.current = {
          content: message,
          fileIds: fileIds,
          eventId: userMessageEvent.event_id
        }
      } else {
        // AI가 응답 중이 아니면 바로 전송
        processEvent(userMessageEvent)
        saveToStorage()

        sendMessage({
          type: 'user_intervene',
          session_id: sessionId.current,
          content: message,
          file_ids: fileIds
        })
      }
    }
  }, [sendMessage, isStopped, isConnected, config, speed, messages, agents, isWaitingForUser, processEvent, saveToStorage, setIsStopped, setIsAIRunning, currentAgent])

  const getConnectionColor = () => {
    switch (connectionState) {
      case 'connected': return 'var(--color-success)'
      case 'connecting': return 'var(--color-warning)'
      case 'error': return 'var(--color-error)'
      default: return 'var(--color-text-tertiary)'
    }
  }

  const getConnectionText = () => {
    switch (connectionState) {
      case 'connected': return '연결됨'
      case 'connecting': return '연결 중...'
      case 'error': return '연결 오류'
      default: return '연결 끊김'
    }
  }

  const totalTokens = tokenUsage.totalInput + tokenUsage.totalOutput

  return (
    <div className="conversation-view">
      {/* Connection Banner */}
      {connectionState !== 'connected' && (
        <div className={`connection-banner ${connectionState}`}>
          <span className="connection-icon">
            <Icons.WifiOff />
          </span>
          <span className="connection-text">{getConnectionText()}</span>
          {connectionState === 'error' && (
            <button className="btn btn-sm" onClick={reconnect}>재연결</button>
          )}
        </div>
      )}

      {/* Safety Warning Banner */}
      {warning && (
        <div className={`warning-banner ${warning.level}`}>
          <span className="warning-icon">
            <Icons.AlertTriangle />
          </span>
          <span className="warning-text">{warning.message}</span>
          {warning.level === 'warning' && (
            <button
              className="btn btn-sm"
              onClick={() => setWarning(null)}
            >
              확인
            </button>
          )}
        </div>
      )}

      {/* Auto-Pause Banner */}
      {autoPausedReason === 'inactive' && isPaused && (
        <div className="auto-pause-banner">
          <span className="auto-pause-icon">
            <Icons.Clock />
          </span>
          <span className="auto-pause-text">
            탭 비활성화로 대화가 자동 일시정지되었습니다
          </span>
          <button className="btn btn-sm btn-primary" onClick={handleResume}>
            재개
          </button>
        </div>
      )}

      {/* Stats Bar */}
      <div className="stats-bar">
        <div className="stat-item">
          <span className="stat-icon"><Icons.Refresh /></span>
          <span className="stat-value">{turnCount}</span>
          <span className="stat-label">턴</span>
        </div>
        <div className="stat-item">
          <span className="stat-icon"><Icons.Users /></span>
          <span className="stat-value">{agents.length}</span>
          <span className="stat-label">AI</span>
        </div>
        <div
          className="stat-item clickable"
          onClick={() => setShowCostDetail(!showCostDetail)}
          title="클릭하여 상세 보기"
        >
          <span className="stat-icon"><Icons.DollarSign /></span>
          <span className="stat-value">{formatCost(estimatedCost)}</span>
          <span className="stat-label">비용</span>
          <span className="stat-expand"><Icons.ChevronDown /></span>
        </div>
        <div
          className="stat-item connection"
          title={getConnectionText()}
        >
          <span
            className="connection-dot"
            style={{ backgroundColor: getConnectionColor() }}
          />
        </div>
      </div>

      {/* Cost Detail Popup */}
      {showCostDetail && (
        <div className="cost-detail-popup">
          <div className="cost-detail-header">
            <h4>사용량 상세</h4>
            <button className="btn-close-popup" onClick={() => setShowCostDetail(false)}>
              <Icons.Close />
            </button>
          </div>
          <div className="cost-detail-body">
            <div className="cost-detail-row">
              <span className="cost-detail-label">총 메시지</span>
              <span className="cost-detail-value">{turnCount}개</span>
            </div>
            <div className="cost-detail-row">
              <span className="cost-detail-label">입력 토큰</span>
              <span className="cost-detail-value">
                {tokenUsage.totalInput > 0 ? formatTokens(tokenUsage.totalInput) : '-'}
              </span>
            </div>
            <div className="cost-detail-row">
              <span className="cost-detail-label">출력 토큰</span>
              <span className="cost-detail-value">
                {tokenUsage.totalOutput > 0 ? formatTokens(tokenUsage.totalOutput) : '-'}
              </span>
            </div>
            <div className="cost-detail-row">
              <span className="cost-detail-label">총 토큰</span>
              <span className="cost-detail-value">
                {totalTokens > 0 ? formatTokens(totalTokens) : '-'}
              </span>
            </div>
            <div className="cost-detail-divider" />
            <div className="cost-detail-row highlight">
              <span className="cost-detail-label">
                {tokenUsage.totalInput > 0 ? '실제 비용' : '예상 비용'}
              </span>
              <span className="cost-detail-value">{formatCost(estimatedCost)}</span>
            </div>
            <div className="cost-detail-row">
              <span className="cost-detail-label">원화 환산</span>
              <span className="cost-detail-value">{formatKRW(estimatedCost)}</span>
            </div>
            {config?.models?.length > 0 && (
              <>
                <div className="cost-detail-divider" />
                <div className="cost-detail-section-title">사용 모델</div>
                {config.models.map(model => {
                  const pricing = MODEL_PRICING[model.id]
                  const modelInfo = AVAILABLE_MODELS.find(m => m.id === model.id)
                  const modelUsage = tokenUsage.history.filter(h => h.model === model.id)
                  const modelTokens = modelUsage.reduce((sum, u) => sum + u.inputTokens + u.outputTokens, 0)
                  return (
                    <div key={model.id} className="cost-model-item">
                      <span className="cost-model-name">{modelInfo?.name || model.id}</span>
                      <span className="cost-model-tokens">
                        {modelTokens > 0 ? formatTokens(modelTokens) : '-'}
                      </span>
                    </div>
                  )
                })}
              </>
            )}
          </div>
        </div>
      )}

      {/* Agent Chips */}
      {agents.length > 0 && (
        <div className="agents-bar">
          {agents.map(agent => (
            <div
              key={agent.id}
              className={`agent-chip ${currentAgent?.id === agent.id ? 'speaking' : ''}`}
              style={{ '--agent-color': agent.color }}
            >
              <span className="agent-indicator" />
              <span className="agent-name">{agent.name}</span>
              <span className="agent-model">{agent.model}</span>
            </div>
          ))}
        </div>
      )}

      {/* Messages Area */}
      <div className="messages-area" ref={messagesAreaRef}>
        {messages.length === 0 && !currentAgent ? (
          <div className="loading-state">
            {isNewConversation ? (
              <>
                <div className="spinner" />
                <p>대화를 준비하는 중...</p>
              </>
            ) : (
              <p style={{ color: 'var(--color-text-secondary)', textAlign: 'center' }}>
                대화 기록이 없습니다.<br />
                <span style={{ fontSize: '14px', opacity: 0.8 }}>
                  아래 입력창에 메시지를 보내 대화를 시작하세요.
                </span>
              </p>
            )}
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <AgentMessage key={msg.id} message={msg} />
            ))}

            {currentAgent && (
              <AgentMessage
                key={`streaming_${currentAgent.id}`}
                message={{
                  agent: currentAgent,
                  content: streamingContent,
                  isStreaming: true
                }}
              />
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Scroll to Bottom Button */}
      {showScrollButton && (
        <button
          className="scroll-to-bottom-btn"
          onClick={scrollToBottom}
          title="최신 메시지로 이동"
        >
          <Icons.ChevronDown />
        </button>
      )}

      {/* User Intervention Bar */}
      <UserInterventionBar
        onSend={handleUserIntervene}
        disabled={false}
        placeholder={
          isWaitingForUser
            ? '메시지를 입력하면 AI가 대화를 이어갑니다...'
            : isStopped
              ? '메시지를 입력하여 대화를 재개하세요...'
              : undefined
        }
      />

      {/* Controls */}
      <ConversationControls
        isPaused={isPaused}
        isStopped={isStopped}
        isAIRunning={isAIRunning}
        isWaitingForUser={isWaitingForUser}
        speed={speed}
        onPause={handlePause}
        onResume={handleResume}
        onStop={handleStop}
        onSpeedChange={handleSpeedChange}
        onEnd={onEnd}
      />

      {/* Status Overlay - 최소화된 UX */}
      {isPaused && !isStopped && !currentAgent && (
        <div className="status-overlay paused">
          <span className="status-icon">||</span>
          <span>일시정지됨</span>
        </div>
      )}
      {/* view 모드에서 대기 중일 때는 오버레이 표시 안 함 (입력창 placeholder로 대체) */}
      {/* 명시적으로 stopped 상태일 때만 오버레이 표시 */}
      {isStopped && !isWaitingForUser && !currentAgent && (
        <div className="status-overlay stopped resumable">
          <span>대화 종료됨</span>
          <span className="status-hint">메시지를 보내 대화를 재개할 수 있습니다</span>
        </div>
      )}
    </div>
  )
}

export default ConversationView
