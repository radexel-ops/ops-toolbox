import { useState } from 'react'
import { API_BASE_URL, PROVIDERS } from '../config'

// SVG Icons
const Icons = {
  Eye: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  ),
  EyeOff: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  ),
  Check: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),
  ExternalLink: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  ),
  Shield: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  ChevronDown: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  ),
  ChevronUp: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="18 15 12 9 6 15" />
    </svg>
  ),
  Close: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  )
}

function SettingsModal({ apiKeys, onSave, onClose }) {
  const [keys, setKeys] = useState({ ...apiKeys })
  const [showKeys, setShowKeys] = useState({
    openai: false,
    google: false,
    anthropic: false,
    xai: false
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [expandedProvider, setExpandedProvider] = useState(null)

  const handleChange = (provider, value) => {
    setKeys(prev => ({ ...prev, [provider]: value }))
    setError(null)
  }

  const toggleShow = (provider) => {
    setShowKeys(prev => ({ ...prev, [provider]: !prev[provider] }))
  }

  const toggleGuide = (providerKey) => {
    setExpandedProvider(expandedProvider === providerKey ? null : providerKey)
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/settings/api-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(keys)
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || `HTTP ${response.status}`)
      }

      onSave(keys)
      onClose()
    } catch (err) {
      console.error('Failed to save API keys:', err)
      setError(err.message || 'API 키 저장에 실패했습니다.')
    } finally {
      setSaving(false)
    }
  }

  const providers = [
    {
      key: 'openai',
      models: 'GPT-5, GPT-5-mini',
      freeCredit: '$5 무료 크레딧',
      ...PROVIDERS.openai
    },
    {
      key: 'google',
      models: 'Gemini 3 Flash, Gemini 3 Pro',
      freeCredit: '무료 사용량 제공',
      ...PROVIDERS.google
    },
    {
      key: 'anthropic',
      models: 'Claude 3 Haiku, Sonnet',
      freeCredit: '$5 무료 크레딧',
      ...PROVIDERS.anthropic
    },
    {
      key: 'xai',
      models: 'Grok Beta',
      freeCredit: '무료 티어 제공',
      ...PROVIDERS.xai
    }
  ]

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content settings-modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2 className="modal-title">API 설정</h2>
            <p className="modal-subtitle">AI 서비스 연동을 위한 API 키 관리</p>
          </div>
          <button className="btn-close" onClick={onClose}>
            <Icons.Close />
          </button>
        </div>

        <div className="modal-body">
          <div className="security-notice">
            <div className="security-notice-icon">
              <Icons.Shield />
            </div>
            <div className="security-notice-content">
              <strong>보안 안내</strong>
              <p>API 키는 현재 세션에만 저장되며, 브라우저 탭을 닫으면 자동으로 삭제됩니다.</p>
            </div>
          </div>

          {error && (
            <div className="error-banner">
              <span className="error-icon">!</span>
              <span>{error}</span>
            </div>
          )}

          <div className="providers-list">
            {providers.map(provider => {
              const hasKey = !!keys[provider.key]
              const isExpanded = expandedProvider === provider.key

              return (
                <div
                  key={provider.key}
                  className={`provider-card ${hasKey ? 'has-key' : ''} ${isExpanded ? 'expanded' : ''}`}
                >
                  <div className="provider-card-header" onClick={() => toggleGuide(provider.key)}>
                    <div className="provider-info">
                      <div
                        className="provider-color-bar"
                        style={{ backgroundColor: provider.color }}
                      />
                      <div className="provider-details">
                        <div className="provider-name-row">
                          <span className="provider-name">{provider.name}</span>
                          {hasKey && (
                            <span className="key-status-badge">
                              <Icons.Check />
                              연결됨
                            </span>
                          )}
                        </div>
                        <span className="provider-models">{provider.models}</span>
                      </div>
                    </div>
                    <div className="provider-expand">
                      {isExpanded ? <Icons.ChevronUp /> : <Icons.ChevronDown />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="provider-card-body">
                      <div className="api-key-guide">
                        <div className="guide-badge">{provider.freeCredit}</div>
                        <div className="guide-steps">
                          <a
                            href={provider.signupUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="guide-step-link"
                          >
                            <span className="step-number">1</span>
                            <span className="step-text">{provider.name} 계정 만들기</span>
                            <span className="step-arrow"><Icons.ExternalLink /></span>
                          </a>
                          <a
                            href={provider.apiKeyUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="guide-step-link primary"
                          >
                            <span className="step-number">2</span>
                            <span className="step-text">API 키 발급받기</span>
                            <span className="step-arrow"><Icons.ExternalLink /></span>
                          </a>
                          <div className="guide-step">
                            <span className="step-number">3</span>
                            <span className="step-text">아래에 키 붙여넣기</span>
                          </div>
                        </div>
                        <div className="guide-links">
                          <a
                            href={provider.pricingUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="guide-link"
                          >
                            요금 정보
                          </a>
                          <a
                            href={provider.docsUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="guide-link"
                          >
                            API 문서
                          </a>
                        </div>
                      </div>

                      <div className="api-key-input-group">
                        <div className="api-key-input-wrapper">
                          <input
                            type={showKeys[provider.key] ? 'text' : 'password'}
                            value={keys[provider.key] || ''}
                            onChange={(e) => handleChange(provider.key, e.target.value)}
                            placeholder={`${provider.keyPrefix}...`}
                            className="api-key-input"
                          />
                          <button
                            type="button"
                            className="btn-toggle-visibility"
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleShow(provider.key)
                            }}
                            title={showKeys[provider.key] ? '숨기기' : '보기'}
                          >
                            {showKeys[provider.key] ? <Icons.EyeOff /> : <Icons.Eye />}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose} disabled={saving}>
            취소
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default SettingsModal
