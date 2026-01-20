// SVG Icons
const Icons = {
  Play: () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  ),
  Pause: () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  ),
  Square: () => (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <rect x="4" y="4" width="16" height="16" rx="2" />
    </svg>
  ),
  RefreshCw: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  )
}

const SPEED_OPTIONS = [
  { value: 'very_fast', label: '2x', title: '매우 빠름' },
  { value: 'fast', label: '1.5x', title: '빠름' },
  { value: 'normal', label: '1x', title: '보통' },
  { value: 'slow', label: '0.7x', title: '느림' },
  { value: 'very_slow', label: '0.5x', title: '매우 느림' },
]

function ConversationControls({
  isPaused,
  isStopped,
  isAIRunning,
  isWaitingForUser,
  speed,
  onPause,
  onResume,
  onStop,
  onSpeedChange,
  onEnd
}) {
  // AI가 실행 중이 아니고, 사용자 입력을 대기 중이면 컨트롤 숨김
  // (view 모드에서 과거 대화를 볼 때)
  const showPlaybackControls = isAIRunning && !isStopped && !isWaitingForUser

  // 완전히 종료된 상태 (stopped이면서 AI도 실행 중이 아님)
  const showStoppedControls = isStopped && !isAIRunning

  // 대기 중 상태 (메시지 입력 대기)
  const showWaitingState = isWaitingForUser && !isStopped

  return (
    <div className="conversation-controls">
      <div className="control-group primary-controls">
        {/* AI 실행 중일 때만 일시정지/재개 버튼 표시 */}
        {showPlaybackControls && (
          <button
            className={`btn-control ${isPaused ? 'paused' : 'playing'}`}
            onClick={isPaused ? onResume : onPause}
            title={isPaused ? '재개' : '일시정지'}
          >
            {isPaused ? <Icons.Play /> : <Icons.Pause />}
          </button>
        )}

        {/* AI 실행 중일 때만 정지 버튼 표시 */}
        {showPlaybackControls && (
          <button
            className="btn-control btn-stop"
            onClick={onStop}
            title="정지"
          >
            <Icons.Square />
          </button>
        )}

        {/* 종료된 상태에서 새 대화 버튼 표시 */}
        {showStoppedControls && (
          <button
            className="btn-control btn-new"
            onClick={onEnd}
            title="새 대화"
          >
            <Icons.RefreshCw />
            <span>새 대화</span>
          </button>
        )}

        {/* 대기 중 상태 표시 (view 모드) */}
        {showWaitingState && (
          <div className="waiting-indicator">
            <span className="waiting-text">메시지를 입력하여 대화 재개</span>
          </div>
        )}
      </div>

      {/* AI 실행 중일 때만 속도 조절 표시 */}
      {showPlaybackControls && (
        <div className="speed-control">
          <span className="speed-label">속도</span>
          <div className="speed-buttons">
            {SPEED_OPTIONS.map(opt => (
              <button
                key={opt.value}
                className={`speed-btn ${speed === opt.value ? 'active' : ''}`}
                onClick={() => onSpeedChange(opt.value)}
                title={opt.title}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default ConversationControls
