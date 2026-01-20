import { useState, useRef, useEffect, useCallback } from 'react'
import {
  AVAILABLE_MODELS,
  SPEED_OPTIONS,
  TOPIC_EXAMPLES,
  MODEL_PRICING,
  PROVIDERS,
  formatCost,
  formatKRW,
  DEFAULT_CONFIG,
  SAFETY_LIMITS,
  API_BASE_URL
} from '../config'

// SVG Icons
const Icons = {
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
  Info: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  ),
  ArrowRight: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  ),
  Paperclip: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  ),
  X: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  ),
  File: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  ),
  Image: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <polyline points="21 15 16 10 5 21" />
    </svg>
  ),
  Send: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  ),
  Upload: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  ),
  Loader: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="spin">
      <line x1="12" y1="2" x2="12" y2="6" />
      <line x1="12" y1="18" x2="12" y2="22" />
      <line x1="4.93" y1="4.93" x2="7.76" y2="7.76" />
      <line x1="16.24" y1="16.24" x2="19.07" y2="19.07" />
      <line x1="2" y1="12" x2="6" y2="12" />
      <line x1="18" y1="12" x2="22" y2="12" />
      <line x1="4.93" y1="19.07" x2="7.76" y2="16.24" />
      <line x1="16.24" y1="7.76" x2="19.07" y2="4.93" />
    </svg>
  )
}

// 에이전트 이름 (master_ai.py와 동일)
const AGENT_NAMES = ["Alpha", "Beta", "Gamma", "Delta", "Echo"]
const AGENT_COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7"]

// 허용 파일 확장자
const ALLOWED_EXTENSIONS = [
  ".txt", ".md", ".csv", ".json", ".xml", ".html", ".css", ".js", ".py",
  ".java", ".cpp", ".c", ".h", ".ts", ".tsx", ".jsx", ".vue", ".svelte",
  ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".r", ".m",
  ".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd",
  ".sql", ".graphql", ".yaml", ".yml", ".toml", ".ini", ".conf", ".cfg",
  ".env", ".gitignore", ".dockerfile", ".makefile", ".log", ".rst", ".tex", ".bib",
  ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf",
  ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff", ".heic",
  ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac",
  ".mp4", ".webm", ".avi", ".mov", ".mkv",
  ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2",
  ".parquet", ".pickle", ".pkl", ".npy", ".npz",
].join(",")

function SetupPanel({ onStart, apiKeys, onOpenSettings }) {
  const [topic, setTopic] = useState('')
  const [agentCount, setAgentCount] = useState(DEFAULT_CONFIG.agentCount)
  const [speed, setSpeed] = useState(DEFAULT_CONFIG.speed)
  const [selectedModels, setSelectedModels] = useState(DEFAULT_CONFIG.models)
  const [estimatedMessages, setEstimatedMessages] = useState(50)
  const [showSafetySettings, setShowSafetySettings] = useState(false)
  const [limits, setLimits] = useState({
    maxTurns: SAFETY_LIMITS.maxTurns,
    maxCost: SAFETY_LIMITS.maxCost,
    maxMinutes: SAFETY_LIMITS.maxMinutes,
    pauseOnInactive: SAFETY_LIMITS.pauseOnInactive
  })

  // 파일 첨부 상태
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const fileInputRef = useRef(null)
  const dropZoneRef = useRef(null)
  const textareaRef = useRef(null)

  // 예상 메시지 수가 변경되면 안전 설정도 자동 조정
  useEffect(() => {
    setLimits(prev => ({ ...prev, maxTurns: estimatedMessages }))
  }, [estimatedMessages])

  // 드래그 앤 드롭 핸들러
  const handleDragEnter = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    // dropZone을 완전히 벗어났을 때만 false로
    if (e.currentTarget === dropZoneRef.current && !e.currentTarget.contains(e.relatedTarget)) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const droppedFiles = Array.from(e.dataTransfer.files)
    if (droppedFiles.length > 0) {
      addFiles(droppedFiles)
    }
  }, [])

  // 파일 추가 (중복 체크)
  const addFiles = (newFiles) => {
    setFiles(prev => {
      const existingNames = new Set(prev.map(f => f.name))
      const uniqueFiles = newFiles.filter(f => !existingNames.has(f.name))
      return [...prev, ...uniqueFiles]
    })
    setUploadError(null)
  }

  const handleModelToggle = (model) => {
    setSelectedModels(prev => {
      const exists = prev.some(m => m.id === model.id)
      if (exists) {
        if (prev.length <= 1) return prev
        return prev.filter(m => m.id !== model.id)
      } else {
        return [...prev, { id: model.id, provider: model.provider }]
      }
    })
  }

  // 파일 업로드
  const uploadFiles = async (fileList) => {
    if (fileList.length === 0) return []

    setUploading(true)
    setUploadError(null)
    try {
      const formData = new FormData()
      fileList.forEach(file => formData.append('files', file))

      const response = await fetch(`${API_BASE_URL}/api/files/upload`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '파일 업로드 실패')
      }

      const result = await response.json()
      return result.files
    } catch (error) {
      console.error('File upload error:', error)
      setUploadError(error.message)
      return []
    } finally {
      setUploading(false)
    }
  }

  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files)
    addFiles(newFiles)
    e.target.value = ''
  }

  const removeFile = (index) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const getFileIcon = (file) => {
    if (file.type.startsWith('image/')) return <Icons.Image />
    return <Icons.File />
  }

  const handleStart = async () => {
    if (!topic.trim() || selectedModels.length === 0) return

    let uploadedFileIds = []
    if (files.length > 0) {
      const uploadedFiles = await uploadFiles(files)
      if (uploadedFiles.length === 0 && files.length > 0) return // 업로드 실패
      uploadedFileIds = uploadedFiles.map(f => f.id)
    }

    onStart({
      topic: topic.trim(),
      agent_count: agentCount,
      speed,
      auto_start: true,
      models: selectedModels,
      limits,
      file_ids: uploadedFileIds
    })
  }

  const handleKeyDown = (e) => {
    // Ctrl/Cmd + Enter로 전송
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      if (topic.trim() && hasApiKey && !uploading) {
        handleStart()
      }
    }
  }

  const handleLimitChange = (key, value) => {
    setLimits(prev => ({ ...prev, [key]: value }))
  }

  // 에이전트-모델 매칭 미리보기 생성
  const agentModelPreview = (() => {
    const preview = []
    for (let i = 0; i < agentCount; i++) {
      const model = selectedModels[i % selectedModels.length]
      const modelInfo = AVAILABLE_MODELS.find(m => m.id === model?.id)
      preview.push({
        agentName: AGENT_NAMES[i],
        agentColor: AGENT_COLORS[i],
        model: modelInfo?.name || model?.id || '미선택',
        provider: PROVIDERS[model?.provider]?.name || ''
      })
    }
    return preview
  })()

  // 사용되지 않는 모델 확인
  const unusedModels = selectedModels.length > agentCount
    ? selectedModels.slice(agentCount).map(m => {
        const modelInfo = AVAILABLE_MODELS.find(mi => mi.id === m.id)
        return modelInfo?.name || m.id
      })
    : []

  // 비용 예측 (누적 컨텍스트 고려)
  const estimatedCost = (() => {
    if (selectedModels.length === 0) return 0

    let totalCost = 0
    const msgsPerModel = estimatedMessages / selectedModels.length

    selectedModels.forEach(model => {
      const pricing = MODEL_PRICING[model.id]
      if (pricing) {
        const N = msgsPerModel
        const base = pricing.avgInputBase || 200
        const avgOut = pricing.avgOutputTokens || 400

        // 누적 입력 토큰: 각 턴마다 이전 출력이 입력에 추가됨
        // 총합 = N*base + avgOut * N*(N-1)/2
        const totalInputTokens = N * base + avgOut * N * (N - 1) / 2
        const totalOutputTokens = N * avgOut

        const inputCost = (totalInputTokens * pricing.input) / 1_000_000
        const outputCost = (totalOutputTokens * pricing.output) / 1_000_000

        totalCost += inputCost + outputCost
      }
    })

    return totalCost
  })()

  const hasApiKey = apiKeys.openai || apiKeys.google
  const canSubmit = topic.trim() && hasApiKey && !uploading && selectedModels.length > 0

  return (
    <div className="setup-panel">
      <div className="setup-container">
        <div className="setup-header">
          <h1 className="setup-title">새 대화 시작</h1>
          <p className="setup-subtitle">AI들이 주제에 대해 자유롭게 대화합니다</p>
        </div>

        {!hasApiKey && (
          <div className="api-key-warning-card">
            <div className="warning-icon">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
              </svg>
            </div>
            <div className="warning-content">
              <div className="warning-title">API 키가 필요합니다</div>
              <div className="warning-desc">대화를 시작하려면 OpenAI 또는 Google AI 키를 설정해주세요</div>
            </div>
            <button className="btn btn-primary" onClick={onOpenSettings}>키 설정</button>
          </div>
        )}

        {/* 통합 입력 영역 - ChatGPT/Claude 스타일 */}
        <div
          ref={dropZoneRef}
          className={`unified-input-container ${isDragging ? 'dragging' : ''} ${!hasApiKey ? 'disabled' : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          {/* 드래그 오버레이 */}
          {isDragging && (
            <div className="drag-overlay">
              <Icons.Upload />
              <span>파일을 여기에 놓으세요</span>
            </div>
          )}

          {/* 첨부된 파일 미리보기 */}
          {files.length > 0 && (
            <div className="attached-files-preview">
              {files.map((file, index) => (
                <div key={`${file.name}-${index}`} className="file-preview-chip">
                  <span className="file-preview-icon">{getFileIcon(file)}</span>
                  <div className="file-preview-info">
                    <span className="file-preview-name" title={file.name}>
                      {file.name.length > 15 ? file.name.slice(0, 12) + '...' + file.name.slice(-5) : file.name}
                    </span>
                    <span className="file-preview-size">{formatFileSize(file.size)}</span>
                  </div>
                  <button
                    className="file-preview-remove"
                    onClick={() => removeFile(index)}
                    disabled={uploading}
                    title="삭제"
                  >
                    <Icons.X />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* 에러 메시지 */}
          {uploadError && (
            <div className="upload-error-inline">
              <span>{uploadError}</span>
              <button onClick={() => setUploadError(null)}><Icons.X /></button>
            </div>
          )}

          {/* 텍스트 입력 영역 */}
          <textarea
            ref={textareaRef}
            className="unified-textarea"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="AI들이 토론할 주제를 입력하세요... (Ctrl+Enter로 시작)"
            maxLength={500}
            disabled={!hasApiKey}
          />

          {/* 입력 하단 툴바 */}
          <div className="unified-input-toolbar">
            <div className="toolbar-left">
              <button
                className="toolbar-btn attach-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading || !hasApiKey}
                title="파일 첨부 (드래그 앤 드롭 가능)"
              >
                {uploading ? <Icons.Loader /> : <Icons.Paperclip />}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileChange}
                accept={ALLOWED_EXTENSIONS}
                style={{ display: 'none' }}
              />
              <span className="char-count">{topic.length}/500</span>
              {files.length > 0 && (
                <span className="file-count">{files.length}개 파일</span>
              )}
            </div>
            <div className="toolbar-right">
              <button
                className={`toolbar-btn send-btn ${canSubmit ? 'active' : ''}`}
                onClick={handleStart}
                disabled={!canSubmit}
                title="대화 시작 (Ctrl+Enter)"
              >
                {uploading ? <Icons.Loader /> : <Icons.Send />}
              </button>
            </div>
          </div>
        </div>

        {/* 주제 추천 */}
        <div className="topic-suggestions-inline">
          <span className="suggestions-label">추천 주제:</span>
          {TOPIC_EXAMPLES.slice(0, 4).map((example, i) => (
            <button
              key={i}
              className="suggestion-chip"
              onClick={() => setTopic(example)}
            >
              {example.length > 20 ? example.slice(0, 20) + '...' : example}
            </button>
          ))}
        </div>

        <div className="setup-card">
          <div className="setup-section">
            <div className="settings-row">
              <div className="setting-group">
                <div className="setting-label">에이전트 수</div>
                <div className="counter-control">
                  <button
                    className="counter-btn"
                    onClick={() => setAgentCount(Math.max(2, agentCount - 1))}
                    disabled={agentCount <= 2}
                  >−</button>
                  <span className="counter-value">{agentCount}</span>
                  <button
                    className="counter-btn"
                    onClick={() => setAgentCount(Math.min(5, agentCount + 1))}
                    disabled={agentCount >= 5}
                  >+</button>
                </div>
              </div>

              <div className="setting-group">
                <div className="setting-label">대화 속도</div>
                <select
                  className="select-control"
                  value={speed}
                  onChange={(e) => setSpeed(e.target.value)}
                >
                  {SPEED_OPTIONS.map(opt => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label} ({opt.description})
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          <div className="setup-section">
            <div className="setup-section-title">AI 모델 선택</div>
            <div className="model-grid">
              {AVAILABLE_MODELS.map(model => {
                const isSelected = selectedModels.some(m => m.id === model.id)
                const provider = PROVIDERS[model.provider]

                return (
                  <div
                    key={model.id}
                    className={`model-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => handleModelToggle(model)}
                  >
                    <div className="model-card-header">
                      <span className="model-provider">{provider?.name}</span>
                      <span className={`model-cost ${model.costTier}`}>
                        {model.costTier === 'low' ? '저렴' : model.costTier === 'medium' ? '보통' : '고비용'}
                      </span>
                    </div>
                    <div className="model-name">{model.name}</div>
                    <div className="model-desc">{model.description}</div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* 에이전트-모델 매칭 미리보기 */}
          <div className="setup-section">
            <div className="setup-section-title">
              <span>대화 참여자 구성</span>
              <span className="section-info-badge">
                <Icons.Info />
                에이전트 {agentCount}명 / 모델 {selectedModels.length}개
              </span>
            </div>

            <div className="agent-preview-container">
              {agentModelPreview.map((agent, idx) => (
                <div key={idx} className="agent-preview-row">
                  <div className="agent-preview-left">
                    <div className="agent-avatar" style={{ backgroundColor: agent.agentColor }}>
                      {agent.agentName[0]}
                    </div>
                    <span className="agent-preview-name">{agent.agentName}</span>
                  </div>
                  <div className="agent-preview-arrow"><Icons.ArrowRight /></div>
                  <div className="agent-preview-model">
                    <span className="agent-model-provider">{agent.provider}</span>
                    <span className="agent-model-name">{agent.model}</span>
                  </div>
                </div>
              ))}
            </div>

            {unusedModels.length > 0 && (
              <div className="unused-models-notice">
                <Icons.Info />
                <span>
                  에이전트 수({agentCount}명)보다 선택한 모델이 많아
                  <strong> {unusedModels.join(', ')}</strong>은(는) 사용되지 않습니다
                </span>
              </div>
            )}

            {selectedModels.length < agentCount && selectedModels.length > 0 && (
              <div className="model-cycle-notice">
                <Icons.Info />
                <span>
                  선택한 모델({selectedModels.length}개)이 에이전트 수({agentCount}명)보다 적어
                  모델이 <strong>순환 배분</strong>됩니다
                </span>
              </div>
            )}
          </div>

          {/* 예상 비용 - 직관적인 새 디자인 */}
          <div className="setup-section">
            <div className="cost-calculator-new">
              {/* 메인 비용 표시 */}
              <div className="cost-main-display">
                <div className="cost-label-row">
                  <span className="cost-label">예상 비용</span>
                  <span className="cost-hint">({estimatedMessages}턴 기준)</span>
                </div>
                <div className="cost-value-row">
                  <span className="cost-usd">{formatCost(estimatedCost)}</span>
                  <span className="cost-krw-display">{formatKRW(estimatedCost)}</span>
                </div>
              </div>

              {/* 턴 수 조절 - 직관적인 컨트롤 */}
              <div className="turn-control">
                <div className="turn-control-header">
                  <span className="turn-label">대화 길이 설정</span>
                </div>
                <div className="turn-control-body">
                  <div className="turn-preset-buttons">
                    {[10, 30, 50, 100, 200, 500].map(val => (
                      <button
                        key={val}
                        className={`turn-preset-btn ${estimatedMessages === val ? 'active' : ''}`}
                        onClick={() => setEstimatedMessages(val)}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                  <div className="turn-slider-row">
                    <input
                      type="range"
                      min="5"
                      max="500"
                      step="1"
                      value={estimatedMessages}
                      onChange={(e) => setEstimatedMessages(Number(e.target.value))}
                      className="turn-slider"
                    />
                    <div className="turn-input-wrapper">
                      <input
                        type="number"
                        min="5"
                        max="500"
                        value={estimatedMessages}
                        onChange={(e) => {
                          const val = Math.max(5, Math.min(500, Number(e.target.value) || 5))
                          setEstimatedMessages(val)
                        }}
                        className="turn-input"
                      />
                      <span className="turn-unit">턴</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 모델별 비용 상세 (접이식) */}
              <details className="cost-breakdown-details">
                <summary className="cost-breakdown-summary">
                  <span>모델별 비용 상세</span>
                  <span className="summary-arrow">
                    <Icons.ChevronDown />
                  </span>
                </summary>
                <div className="cost-breakdown-content">
                  {selectedModels.map(model => {
                    const pricing = MODEL_PRICING[model.id]
                    const modelInfo = AVAILABLE_MODELS.find(m => m.id === model.id)
                    if (!pricing) return null

                    const N = estimatedMessages / selectedModels.length
                    const base = pricing.avgInputBase || 200
                    const avgOut = pricing.avgOutputTokens || 400
                    const totalInputTokens = N * base + avgOut * N * (N - 1) / 2
                    const totalOutputTokens = N * avgOut
                    const modelCost = (totalInputTokens * pricing.input + totalOutputTokens * pricing.output) / 1_000_000

                    return (
                      <div key={model.id} className="cost-breakdown-item">
                        <div className="breakdown-model-name">{modelInfo?.name || model.id}</div>
                        <div className="breakdown-details">
                          <span className="breakdown-rate">
                            입력 ${pricing.input}/M · 출력 ${pricing.output}/M
                          </span>
                          <span className="breakdown-cost">{formatCost(modelCost)}</span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </details>

              {/* 안전 설정 (접이식) */}
              <details className="safety-details">
                <summary className="safety-summary-header">
                  <div className="safety-summary-left">
                    <Icons.Shield />
                    <span>안전 설정</span>
                  </div>
                  <div className="safety-summary-right">
                    <span className="safety-badge">최대 {limits.maxTurns}턴 / ${limits.maxCost} / {limits.maxMinutes}분</span>
                    <span className="summary-arrow"><Icons.ChevronDown /></span>
                  </div>
                </summary>
                <div className="safety-settings-content">
                  <div className="safety-setting-item">
                    <span className="setting-name">최대 턴 수</span>
                    <div className="setting-control">
                      <input
                        type="number"
                        min="10"
                        max="1000"
                        value={limits.maxTurns}
                        onChange={(e) => handleLimitChange('maxTurns', Math.max(10, Math.min(1000, Number(e.target.value) || 10)))}
                        className="setting-input"
                      />
                      <span className="setting-unit">회</span>
                    </div>
                  </div>

                  <div className="safety-setting-item">
                    <span className="setting-name">최대 비용</span>
                    <select
                      value={limits.maxCost}
                      onChange={(e) => handleLimitChange('maxCost', Number(e.target.value))}
                      className="setting-select"
                    >
                      <option value={0.5}>$0.50</option>
                      <option value={1}>$1.00</option>
                      <option value={2}>$2.00</option>
                      <option value={5}>$5.00</option>
                      <option value={10}>$10.00</option>
                    </select>
                  </div>

                  <div className="safety-setting-item">
                    <span className="setting-name">최대 시간</span>
                    <select
                      value={limits.maxMinutes}
                      onChange={(e) => handleLimitChange('maxMinutes', Number(e.target.value))}
                      className="setting-select"
                    >
                      <option value={15}>15분</option>
                      <option value={30}>30분</option>
                      <option value={60}>1시간</option>
                      <option value={120}>2시간</option>
                    </select>
                  </div>

                  <div className="safety-setting-item">
                    <span className="setting-name">비활성 시 자동 일시정지</span>
                    <label className="toggle-switch-new">
                      <input
                        type="checkbox"
                        checked={limits.pauseOnInactive}
                        onChange={(e) => handleLimitChange('pauseOnInactive', e.target.checked)}
                      />
                      <span className="toggle-track"></span>
                    </label>
                  </div>
                </div>
              </details>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default SetupPanel
