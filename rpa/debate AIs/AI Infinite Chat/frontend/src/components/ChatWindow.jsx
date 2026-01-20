import { useState, useEffect, useRef } from 'react'
import MessageBubble from './MessageBubble'
import InputBar from './InputBar'
import useWebSocket from '../hooks/useWebSocket'

function ChatWindow({ apiKey, selectedModel }) {
  const [messages, setMessages] = useState([])
  const [isTyping, setIsTyping] = useState(false)
  const [currentResponse, setCurrentResponse] = useState('')
  const messagesEndRef = useRef(null)

  const { isConnected, sendMessage, lastMessage } = useWebSocket('ws://localhost:8000/ws/chat')

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage) return

    const data = lastMessage

    switch (data.type) {
      case 'user_message':
        setMessages(prev => [...prev, {
          id: Date.now(),
          role: 'user',
          content: data.content
        }])
        break

      case 'ai_start':
        setIsTyping(true)
        setCurrentResponse('')
        break

      case 'token':
        setCurrentResponse(prev => prev + data.content)
        break

      case 'ai_complete':
        setIsTyping(false)
        setMessages(prev => [...prev, {
          id: Date.now(),
          role: 'ai',
          content: data.content,
          model: data.model
        }])
        setCurrentResponse('')
        break

      case 'error':
        setIsTyping(false)
        setMessages(prev => [...prev, {
          id: Date.now(),
          role: 'ai',
          content: `Error: ${data.content}`,
          isError: true
        }])
        break
    }
  }, [lastMessage])

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentResponse])

  const handleSend = (text) => {
    if (!text.trim() || !isConnected) return

    sendMessage({
      type: 'message',
      content: text,
      model: selectedModel
    })
  }

  return (
    <div className="chat-window">
      <div className="connection-status">
        <span className={`status-dot ${isConnected ? 'connected' : 'disconnected'}`}></span>
        {isConnected ? 'Connected' : 'Disconnected'}
      </div>

      <div className="messages-container">
        {messages.length === 0 && !isTyping ? (
          <div className="empty-state">
            <h3>Start a conversation</h3>
            <p>Type a message below to begin chatting with AI</p>
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))}

            {/* Streaming response */}
            {isTyping && currentResponse && (
              <MessageBubble
                message={{
                  role: 'ai',
                  content: currentResponse,
                  isStreaming: true
                }}
              />
            )}

            {/* Typing indicator */}
            {isTyping && !currentResponse && (
              <div className="message ai">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      <InputBar
        onSend={handleSend}
        disabled={!isConnected || isTyping}
      />
    </div>
  )
}

export default ChatWindow
