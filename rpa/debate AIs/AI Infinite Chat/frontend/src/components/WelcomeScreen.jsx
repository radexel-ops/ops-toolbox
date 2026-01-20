import { useState } from 'react'

function WelcomeScreen({ onComplete, onOpenSettings }) {
  const [step, setStep] = useState(0)

  const steps = [
    {
      title: 'AI Infinite Chat에 오신 것을 환영합니다',
      description: '여러 AI가 당신이 던진 주제에 대해 무한히 대화하는 것을 지켜보세요.',
      icon: '🤖',
      features: [
        '다양한 AI 모델 (GPT, Gemini) 지원',
        '실시간 대화 스트리밍',
        '대화 중 언제든 개입 가능'
      ]
    },
    {
      title: '시작하기 전에',
      description: 'AI 서비스를 사용하려면 API 키가 필요합니다.',
      icon: '🔑',
      features: [
        'OpenAI 또는 Google AI 계정 필요',
        'API 키는 브라우저 세션에만 저장 (보안)',
        '탭을 닫으면 키가 자동 삭제됩니다'
      ],
      action: {
        label: 'API 키 설정하기',
        onClick: onOpenSettings
      }
    },
    {
      title: '사용 방법',
      description: '간단한 3단계로 AI 대화를 시작하세요.',
      icon: '📝',
      steps: [
        { number: '1', title: '주제 입력', desc: '토론하고 싶은 주제를 입력하세요' },
        { number: '2', title: '설정 선택', desc: 'AI 수, 속도, 모델을 선택하세요' },
        { number: '3', title: '대화 시작', desc: 'AI들이 자동으로 대화를 시작합니다' }
      ]
    },
    {
      title: '대화 중 컨트롤',
      description: '대화 중에도 다양한 제어가 가능합니다.',
      icon: '🎮',
      controls: [
        { icon: '⏸️', name: '일시정지', desc: '대화를 잠시 멈춤' },
        { icon: '⏹️', name: '정지', desc: '대화 완전 종료' },
        { icon: '⚡', name: '속도 조절', desc: '대화 속도 변경' },
        { icon: '💬', name: '개입', desc: '대화에 직접 참여' }
      ]
    }
  ]

  const currentStep = steps[step]
  const isLastStep = step === steps.length - 1

  return (
    <div className="welcome-screen">
      <div className="welcome-content">
        {/* 진행 표시 */}
        <div className="welcome-progress">
          {steps.map((_, index) => (
            <div
              key={index}
              className={`progress-dot ${index === step ? 'active' : ''} ${index < step ? 'completed' : ''}`}
            />
          ))}
        </div>

        {/* 아이콘 */}
        <div className="welcome-icon">{currentStep.icon}</div>

        {/* 제목 & 설명 */}
        <h2 className="welcome-title">{currentStep.title}</h2>
        <p className="welcome-description">{currentStep.description}</p>

        {/* 기능 목록 */}
        {currentStep.features && (
          <ul className="welcome-features">
            {currentStep.features.map((feature, i) => (
              <li key={i}>
                <span className="feature-check">✓</span>
                {feature}
              </li>
            ))}
          </ul>
        )}

        {/* 단계 안내 */}
        {currentStep.steps && (
          <div className="welcome-steps">
            {currentStep.steps.map((s) => (
              <div key={s.number} className="step-item">
                <div className="step-number">{s.number}</div>
                <div className="step-content">
                  <div className="step-title">{s.title}</div>
                  <div className="step-desc">{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 컨트롤 안내 */}
        {currentStep.controls && (
          <div className="welcome-controls">
            {currentStep.controls.map((ctrl) => (
              <div key={ctrl.name} className="control-item">
                <span className="control-icon">{ctrl.icon}</span>
                <div className="control-info">
                  <span className="control-name">{ctrl.name}</span>
                  <span className="control-desc">{ctrl.desc}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 액션 버튼 */}
        {currentStep.action && (
          <button
            className="btn-secondary welcome-action"
            onClick={currentStep.action.onClick}
          >
            {currentStep.action.label}
          </button>
        )}

        {/* 네비게이션 */}
        <div className="welcome-nav">
          {step > 0 && (
            <button
              className="btn-secondary"
              onClick={() => setStep(step - 1)}
            >
              이전
            </button>
          )}
          <button
            className="btn-primary"
            onClick={() => isLastStep ? onComplete() : setStep(step + 1)}
          >
            {isLastStep ? '시작하기' : '다음'}
          </button>
        </div>

        {/* 건너뛰기 */}
        {!isLastStep && (
          <button
            className="btn-skip"
            onClick={onComplete}
          >
            건너뛰기
          </button>
        )}
      </div>
    </div>
  )
}

export default WelcomeScreen
