import { useState, useEffect, useCallback, useRef } from 'react'

let globalMessageId = 0 // 전역 메시지 ID 카운터

function useWebSocket(url) {
  const [isConnected, setIsConnected] = useState(false)
  // 메시지 큐 기반 접근 - 빠른 메시지 도착 시 손실 방지
  const [messageQueue, setMessageQueue] = useState([])
  const [lastMessage, setLastMessage] = useState(null)
  const [connectionState, setConnectionState] = useState('disconnected') // 'connecting', 'connected', 'disconnected', 'error'
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const reconnectAttempts = useRef(0)
  const maxReconnectAttempts = 5
  const processedMessageIds = useRef(new Set()) // 이미 처리된 메시지 ID 추적

  const connect = useCallback(() => {
    // 이미 연결 중이거나 연결된 상태면 무시
    if (wsRef.current && (wsRef.current.readyState === WebSocket.CONNECTING || wsRef.current.readyState === WebSocket.OPEN)) {
      return
    }

    try {
      setConnectionState('connecting')
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('[WS] Connected')
        setIsConnected(true)
        setConnectionState('connected')
        reconnectAttempts.current = 0 // 연결 성공 시 재시도 횟수 리셋
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          // 각 메시지에 고유 ID 부여
          const messageId = ++globalMessageId
          data._msgId = messageId
          data._timestamp = Date.now()

          console.log('[WS Recv]', data.type, `(id:${messageId})`, data)

          // 메시지를 큐에 추가 (함수형 업데이트로 손실 방지)
          setMessageQueue(prev => [...prev, data])
        } catch (e) {
          console.error('[WS] Failed to parse message:', e)
        }
      }

      ws.onclose = (event) => {
        console.log('[WS] Disconnected, code:', event.code, 'reason:', event.reason)
        setIsConnected(false)
        setConnectionState('disconnected')

        // 정상 종료가 아니고 재시도 횟수 미만이면 재연결
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000) // 지수 백오프, 최대 10초
          console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current + 1}/${maxReconnectAttempts})`)

          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttempts.current++
            connect()
          }, delay)
        } else if (reconnectAttempts.current >= maxReconnectAttempts) {
          console.error('[WS] Max reconnection attempts reached')
          setConnectionState('error')
        }
      }

      ws.onerror = (error) => {
        console.error('[WS] Error:', error)
        setConnectionState('error')
      }

      wsRef.current = ws
    } catch (error) {
      console.error('[WS] Failed to connect:', error)
      setConnectionState('error')
    }
  }, [url])

  useEffect(() => {
    connect()

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  // 메시지 큐 처리 - 순차적으로 lastMessage에 전달
  useEffect(() => {
    if (messageQueue.length > 0) {
      // 첫 번째 메시지를 가져와서 lastMessage로 설정
      const nextMessage = messageQueue[0]
      setLastMessage(nextMessage)
      // 큐에서 첫 번째 메시지 제거
      setMessageQueue(prev => prev.slice(1))
    }
  }, [messageQueue])

  const sendMessage = useCallback((data) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      console.log('[WS Send]', data.type, data)
      wsRef.current.send(JSON.stringify(data))
      return true
    } else {
      console.warn('[WS Send Failed] Not connected', data.type)
      return false
    }
  }, [])

  // 수동 재연결 함수
  const reconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close(1000) // 정상 종료 코드
    }
    reconnectAttempts.current = 0
    setTimeout(connect, 100)
  }, [connect])

  // 연결 종료 함수
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    reconnectAttempts.current = maxReconnectAttempts // 재연결 방지
    if (wsRef.current) {
      wsRef.current.close(1000)
    }
  }, [])

  return { isConnected, connectionState, lastMessage, sendMessage, reconnect, disconnect }
}

export default useWebSocket
