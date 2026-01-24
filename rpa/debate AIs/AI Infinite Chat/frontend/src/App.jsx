import { useState, useEffect, useCallback, useRef } from 'react'
import './App.css'
import { STORAGE_KEYS } from './config'
import {
  initDB,
  getAllConversations,
  getConversation,
  saveConversation,
  deleteConversation,
  createConversation,
  formatDate
} from './services/storage'
import SetupPanel from './components/SetupPanel'
import ConversationView from './components/ConversationView'
import SettingsModal from './components/SettingsModal'
import ErrorBoundary from './components/ErrorBoundary'

// SVG Icons
const Icons = {
  Logo: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  ),
  Plus: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  ),
  Message: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
    </svg>
  ),
  Settings: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  Trash: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
    </svg>
  ),
  Menu: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  ),
  Key: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  )
}

function AppContent() {
  // State
  const [conversations, setConversations] = useState([])
  const [currentConversationId, setCurrentConversationId] = useState(null)
  const [currentConversation, setCurrentConversation] = useState(null)
  const [view, setView] = useState('setup') // 'setup', 'conversation'
  const [conversationMode, setConversationMode] = useState(null) // 'new' (새 대화 시작) | 'view' (기존 대화 보기)
  const [showSettings, setShowSettings] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [apiKeys, setApiKeys] = useState({ openai: '', google: '' })
  const [isFirstVisit, setIsFirstVisit] = useState(false)

  // Initialize
  useEffect(() => {
    const init = async () => {
      // Initialize IndexedDB
      await initDB()

      // Load conversations
      const convs = await getAllConversations()
      setConversations(convs)

      // Load API keys from session
      const savedKeys = sessionStorage.getItem(STORAGE_KEYS.API_KEYS)
      if (savedKeys) {
        try {
          setApiKeys(JSON.parse(savedKeys))
        } catch (e) {
          console.error('Failed to parse saved API keys')
        }
      }

      // Check backend for configured API keys (from environment variables)
      try {
        const response = await fetch('http://localhost:8000/api/settings')
        if (response.ok) {
          const settings = await response.json()
          if (settings.configured_providers && settings.configured_providers.length > 0) {
            // Backend has API keys configured, update local state
            const backendKeys = {}
            settings.configured_providers.forEach(provider => {
              backendKeys[provider] = 'configured' // Mark as configured (actual key is on backend)
            })
            setApiKeys(prev => ({ ...prev, ...backendKeys }))
            console.log('[App] Backend API keys detected:', settings.configured_providers)
          }
        }
      } catch (e) {
        console.error('[App] Failed to check backend API keys:', e)
      }

      // Check first visit
      const firstVisit = localStorage.getItem(STORAGE_KEYS.FIRST_VISIT)
      if (!firstVisit) {
        setIsFirstVisit(true)
        localStorage.setItem(STORAGE_KEYS.FIRST_VISIT, 'false')
      }
    }

    init()
  }, [])

  // Save API keys
  const saveApiKeys = useCallback((keys) => {
    setApiKeys(keys)
    sessionStorage.setItem(STORAGE_KEYS.API_KEYS, JSON.stringify(keys))

    // Send to backend
    fetch('http://localhost:8000/api/settings/api-keys', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(keys)
    }).catch(console.error)
  }, [])

  // Handle new conversation start
  const handleStartConversation = useCallback(async (config) => {
    const conversation = createConversation(config)
    await saveConversation(conversation)

    setCurrentConversation(conversation)
    setCurrentConversationId(conversation.id)
    setConversationMode('new') // 새 대화 시작 모드
    setView('conversation')

    // Refresh conversation list
    const convs = await getAllConversations()
    setConversations(convs)
  }, [])

  // Handle conversation update (from ConversationView)
  // 주의: ConversationView가 이미 IndexedDB에 저장함
  // 여기서는 React 상태만 동기화하고, 목록만 새로고침
  const handleConversationUpdate = useCallback(async (updates) => {
    if (!currentConversationId) return

    try {
      // IndexedDB에서 최신 대화 불러오기 (ConversationView가 저장한 최신 데이터)
      const latestConversation = await getConversation(currentConversationId)
      if (latestConversation) {
        // React 상태를 최신 데이터로 동기화
        setCurrentConversation(latestConversation)
        console.log('[App] Synced conversation state from IndexedDB:', currentConversationId, 'messages:', latestConversation.messages?.length)
      }

      // 목록 새로고침
      const convs = await getAllConversations()
      setConversations(convs)
    } catch (err) {
      console.error('[App] Failed to sync conversation:', err)
    }
  }, [currentConversationId])

  // 대화 로딩 중 상태 추적 (중복 클릭 방지)
  const loadingConversationRef = useRef(false)

  // Load existing conversation (기존 대화 보기)
  const handleLoadConversation = useCallback(async (id) => {
    // 이미 로딩 중이면 무시 (빠른 클릭으로 인한 깜빡임 방지)
    if (loadingConversationRef.current) {
      console.log('[App] Already loading conversation, ignoring click')
      return
    }

    // 이미 같은 대화를 보고 있으면 무시
    if (currentConversationId === id && view === 'conversation') {
      console.log('[App] Same conversation already viewing')
      setSidebarOpen(false)
      return
    }

    loadingConversationRef.current = true

    try {
      const conversation = await getConversation(id)
      if (conversation) {
        // 상태를 배치로 업데이트 (React 18에서 자동 배치됨)
        setCurrentConversation(conversation)
        setCurrentConversationId(id)
        setConversationMode('view') // 기존 대화 보기 모드 - AI 자동 시작 안 함
        setView('conversation')
        setSidebarOpen(false)
        console.log('[App] Loaded conversation:', id, 'messages:', conversation.messages?.length)
      }
    } catch (error) {
      console.error('[App] Failed to load conversation:', error)
    } finally {
      // 약간의 지연 후 로딩 플래그 해제 (상태 업데이트 완료 대기)
      setTimeout(() => {
        loadingConversationRef.current = false
      }, 100)
    }
  }, [currentConversationId, view])

  // Delete conversation
  const handleDeleteConversation = useCallback(async (id, e) => {
    e.stopPropagation()
    await deleteConversation(id)

    if (currentConversationId === id) {
      setCurrentConversation(null)
      setCurrentConversationId(null)
      setView('setup')
    }

    const convs = await getAllConversations()
    setConversations(convs)
  }, [currentConversationId])

  // New conversation
  const handleNewConversation = useCallback(() => {
    setCurrentConversation(null)
    setCurrentConversationId(null)
    setConversationMode(null)
    setView('setup')
    setSidebarOpen(false)
  }, [])

  // Stop conversation and go back
  const handleStopConversation = useCallback(() => {
    setView('setup')
    setCurrentConversation(null)
    setCurrentConversationId(null)
    setConversationMode(null)
  }, [])

  const hasApiKey = apiKeys.openai || apiKeys.google

  return (
    <div className="app">
      {/* Sidebar Backdrop (Mobile) */}
      <div
        className={`sidebar-backdrop ${sidebarOpen ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="logo">
            <div className="logo-icon">
              <Icons.Logo />
            </div>
            <span className="logo-text">AI Chat</span>
          </div>
          <button className="btn-new-chat" onClick={handleNewConversation} title="새 대화">
            <Icons.Plus />
          </button>
        </div>

        <div className="conversation-list">
          {conversations.length === 0 ? (
            <div className="empty-state" style={{ padding: '40px 20px' }}>
              <p style={{ fontSize: '13px', color: 'var(--color-text-tertiary)' }}>
                대화 기록이 없습니다
              </p>
            </div>
          ) : (
            <>
              <div className="conversation-list-header">최근 대화</div>
              {conversations.map(conv => (
                <div
                  key={conv.id}
                  className={`conversation-item ${currentConversationId === conv.id ? 'active' : ''}`}
                  onClick={() => handleLoadConversation(conv.id)}
                >
                  <div className="conversation-item-icon">
                    <Icons.Message />
                  </div>
                  <div className="conversation-item-content">
                    <div className="conversation-item-title">
                      {conv.topic.length > 30 ? conv.topic.slice(0, 30) + '...' : conv.topic}
                    </div>
                    <div className="conversation-item-meta">
                      <span className="conversation-item-date">{formatDate(conv.updatedAt)}</span>
                      <span className="conversation-item-count">{conv.messages?.length || 0}</span>
                    </div>
                  </div>
                  <div className="conversation-item-actions">
                    <button
                      className="btn-item-action danger"
                      onClick={(e) => handleDeleteConversation(conv.id, e)}
                      title="삭제"
                    >
                      <Icons.Trash />
                    </button>
                  </div>
                </div>
              ))}
            </>
          )}
        </div>

        <div className="sidebar-footer">
          <button className="btn-settings" onClick={() => setShowSettings(true)}>
            <Icons.Settings />
            <span>설정</span>
            {!hasApiKey && (
              <span style={{
                marginLeft: 'auto',
                width: 8,
                height: 8,
                background: 'var(--color-warning)',
                borderRadius: '50%'
              }} />
            )}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {/* Header */}
        <header className="main-header">
          <div className="header-left">
            <button className="btn-menu" onClick={() => setSidebarOpen(true)}>
              <Icons.Menu />
            </button>
            {view === 'conversation' && currentConversation && (
              <div className="topic-display">
                <span className="topic-label">주제</span>
                <span className="topic-text">{currentConversation.topic}</span>
              </div>
            )}
          </div>
          <div className="header-right">
            {!hasApiKey && (
              <button
                className="btn btn-api-key-warning"
                onClick={() => setShowSettings(true)}
              >
                <Icons.Key />
                <span>API 키</span>
              </button>
            )}
          </div>
        </header>

        {/* Content */}
        {view === 'setup' ? (
          <SetupPanel
            onStart={handleStartConversation}
            apiKeys={apiKeys}
            onOpenSettings={() => setShowSettings(true)}
          />
        ) : (
          <ConversationView
            key={currentConversation?.id}
            conversation={currentConversation}
            config={currentConversation}
            mode={conversationMode} // 'new' (새 대화 시작) | 'view' (기존 대화 보기)
            onUpdate={handleConversationUpdate}
            onEnd={handleStopConversation}
          />
        )}
      </main>

      {/* Settings Modal */}
      {showSettings && (
        <SettingsModal
          apiKeys={apiKeys}
          onSave={saveApiKeys}
          onClose={() => setShowSettings(false)}
        />
      )}

      {/* First Visit Prompt */}
      {isFirstVisit && !hasApiKey && (
        <div className="modal-overlay" onClick={() => setIsFirstVisit(false)}>
          <div className="onboarding-card" onClick={e => e.stopPropagation()}>
            <div className="onboarding-icon">
              <Icons.Key />
            </div>
            <h2 className="onboarding-title">시작하기</h2>
            <p className="onboarding-desc">
              AI 대화를 시작하려면 API 키가 필요합니다.
              <br />무료로 발급받을 수 있습니다.
            </p>

            <div className="onboarding-steps">
              <div className="onboarding-step">
                <div className="step-number">1</div>
                <div className="step-content">
                  <h4>API 키 발급</h4>
                  <p>OpenAI 또는 Google AI에서 무료 발급</p>
                </div>
              </div>
              <div className="onboarding-step">
                <div className="step-number">2</div>
                <div className="step-content">
                  <h4>키 입력</h4>
                  <p>설정에서 발급받은 키를 입력</p>
                </div>
              </div>
              <div className="onboarding-step">
                <div className="step-number">3</div>
                <div className="step-content">
                  <h4>대화 시작</h4>
                  <p>주제를 입력하고 AI 대화 시작</p>
                </div>
              </div>
            </div>

            <div className="onboarding-actions">
              <button
                className="btn-cta"
                onClick={() => {
                  setIsFirstVisit(false)
                  setShowSettings(true)
                }}
              >
                API 키 설정하기
              </button>
              <button
                className="btn-skip"
                onClick={() => setIsFirstVisit(false)}
              >
                나중에 하기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// Wrap with error boundary
function App() {
  return (
    <ErrorBoundary>
      <AppContent />
    </ErrorBoundary>
  )
}

export default App
