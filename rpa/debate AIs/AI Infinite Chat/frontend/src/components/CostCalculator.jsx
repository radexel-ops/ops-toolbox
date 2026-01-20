import { useState, useEffect, useMemo } from 'react'
import { MODEL_PRICING, AVAILABLE_MODELS, PROVIDERS } from '../config'

/**
 * 비용 계산기 컴포넌트
 * - 선택한 모델의 예상 비용 표시
 * - 메시지 수 기반 비용 예측
 * - 실시간 사용량 추적
 */
function CostCalculator({
  selectedModels = [],
  messageCount = 0,
  estimatedMessages = 100,
  onEstimateChange
}) {
  const [showDetails, setShowDetails] = useState(false)
  const [customEstimate, setCustomEstimate] = useState(estimatedMessages)

  // 모델별 비용 계산
  const costBreakdown = useMemo(() => {
    if (selectedModels.length === 0) return null

    const breakdown = selectedModels.map(modelId => {
      const pricing = MODEL_PRICING[modelId]
      const modelInfo = AVAILABLE_MODELS.find(m => m.id === modelId)

      if (!pricing || !modelInfo) return null

      const avgOutput = pricing.avgOutputTokens || 400
      const avgInputBase = pricing.avgInputBase || 200

      // 간단화된 1턴 비용 (첫 턴 기준)
      const firstTurnCost = (avgInputBase * pricing.input + avgOutput * pricing.output) / 1_000_000

      return {
        modelId,
        modelName: modelInfo.name,
        provider: modelInfo.provider,
        costPerFirstTurn: firstTurnCost,
        pricing,
        avgOutput,
        avgInputBase
      }
    }).filter(Boolean)

    return breakdown
  }, [selectedModels])

  // 총 예상 비용 계산 (누적 컨텍스트 고려)
  // 대화에서 입력 토큰은 이전 대화 기록이 누적되므로 점점 증가함
  const totalEstimatedCost = useMemo(() => {
    if (!costBreakdown || costBreakdown.length === 0) return 0

    // 각 에이전트가 동일하게 메시지를 보낸다고 가정
    const msgsPerAgent = customEstimate / costBreakdown.length

    return costBreakdown.reduce((total, item) => {
      const N = msgsPerAgent
      const base = item.avgInputBase
      const avgOut = item.avgOutput

      // 누적 입력 토큰: 각 턴마다 이전 출력이 입력에 추가됨
      // turn 1: base
      // turn 2: base + avgOut
      // turn 3: base + 2*avgOut
      // ...
      // turn N: base + (N-1)*avgOut
      // 총합 = N*base + avgOut * (0 + 1 + 2 + ... + N-1) = N*base + avgOut * N*(N-1)/2
      const totalInputTokens = N * base + avgOut * N * (N - 1) / 2

      // 총 출력 토큰
      const totalOutputTokens = N * avgOut

      // 비용 계산
      const inputCost = (totalInputTokens * item.pricing.input) / 1_000_000
      const outputCost = (totalOutputTokens * item.pricing.output) / 1_000_000

      return total + inputCost + outputCost
    }, 0)
  }, [costBreakdown, customEstimate])

  // 현재 사용량 비용 (누적 컨텍스트 고려)
  const currentCost = useMemo(() => {
    if (!costBreakdown || costBreakdown.length === 0) return 0

    const msgsPerAgent = messageCount / costBreakdown.length

    return costBreakdown.reduce((total, item) => {
      const N = msgsPerAgent
      const base = item.avgInputBase
      const avgOut = item.avgOutput

      const totalInputTokens = N * base + avgOut * N * (N - 1) / 2
      const totalOutputTokens = N * avgOut

      const inputCost = (totalInputTokens * item.pricing.input) / 1_000_000
      const outputCost = (totalOutputTokens * item.pricing.output) / 1_000_000

      return total + inputCost + outputCost
    }, 0)
  }, [costBreakdown, messageCount])

  // 비용 티어 라벨
  const getCostTierLabel = (cost) => {
    if (cost < 0.01) return { label: '매우 저렴', color: '#34c759' }
    if (cost < 0.05) return { label: '저렴', color: '#30d158' }
    if (cost < 0.20) return { label: '보통', color: '#ff9500' }
    if (cost < 1.00) return { label: '다소 비쌈', color: '#ff6b00' }
    return { label: '고비용', color: '#ff3b30' }
  }

  const formatCost = (cost) => {
    if (cost < 0.001) return '< $0.001'
    if (cost < 0.01) return `$${cost.toFixed(4)}`
    if (cost < 1) return `$${cost.toFixed(3)}`
    return `$${cost.toFixed(2)}`
  }

  const formatKRW = (usd) => {
    const krw = usd * 1350 // 대략적인 환율
    if (krw < 1) return '< 1원'
    if (krw < 100) return `약 ${Math.round(krw)}원`
    return `약 ${Math.round(krw).toLocaleString()}원`
  }

  if (selectedModels.length === 0) {
    return null
  }

  return (
    <div className="cost-calculator">
      <div className="cost-header" onClick={() => setShowDetails(!showDetails)}>
        <div className="cost-title">
          <span className="cost-icon">💰</span>
          <span>예상 비용</span>
        </div>
        <div className="cost-summary">
          <span className="cost-amount">{formatCost(totalEstimatedCost)}</span>
          <span className="cost-krw">({formatKRW(totalEstimatedCost)})</span>
          <span className={`cost-toggle ${showDetails ? 'open' : ''}`}>▼</span>
        </div>
      </div>

      {showDetails && (
        <div className="cost-details">
          {/* 메시지 수 슬라이더 */}
          <div className="estimate-control">
            <label>예상 메시지 수 (최대 턴)</label>
            <div className="slider-row">
              <input
                type="range"
                min="1"
                max="500"
                step="1"
                value={customEstimate}
                onChange={(e) => {
                  const val = parseInt(e.target.value)
                  setCustomEstimate(val)
                  onEstimateChange?.(val)
                }}
              />
              <input
                type="number"
                min="1"
                max="500"
                value={customEstimate}
                onChange={(e) => {
                  const val = Math.max(1, Math.min(500, parseInt(e.target.value) || 1))
                  setCustomEstimate(val)
                  onEstimateChange?.(val)
                }}
                className="estimate-input"
              />
              <span className="estimate-unit">턴</span>
            </div>
          </div>

          {/* 모델별 비용 상세 */}
          <div className="cost-breakdown">
            <h4>모델별 비용 (토큰 단가)</h4>
            {costBreakdown?.map(item => {
              const provider = PROVIDERS[item.provider]
              // 100턴 기준 평균 비용으로 티어 판단
              const avgCostPer100 = (
                (100 * item.avgInputBase + item.avgOutput * 100 * 99 / 2) * item.pricing.input / 1_000_000 +
                (100 * item.avgOutput) * item.pricing.output / 1_000_000
              )
              const tierInfo = getCostTierLabel(avgCostPer100)

              return (
                <div key={item.modelId} className="cost-item">
                  <div className="cost-item-header">
                    <span className="model-icon">{provider?.icon}</span>
                    <span className="model-name">{item.modelName}</span>
                    <span
                      className="cost-tier"
                      style={{ color: tierInfo.color }}
                    >
                      {tierInfo.label}
                    </span>
                  </div>
                  <div className="cost-item-details">
                    <div className="pricing-row">
                      <span>입력: ${item.pricing.input}/1M tokens</span>
                      <span>출력: ${item.pricing.output}/1M tokens</span>
                    </div>
                    <div className="per-msg-cost">
                      첫 턴: {formatCost(item.costPerFirstTurn)} | 100턴 누적: {formatCost(avgCostPer100)}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* 현재 사용량 (대화 중일 때만) */}
          {messageCount > 0 && (
            <div className="current-usage">
              <h4>현재 사용량</h4>
              <div className="usage-stats">
                <div className="usage-item">
                  <span className="usage-label">메시지</span>
                  <span className="usage-value">{messageCount}개</span>
                </div>
                <div className="usage-item">
                  <span className="usage-label">현재 비용</span>
                  <span className="usage-value cost">{formatCost(currentCost)}</span>
                </div>
              </div>
            </div>
          )}

          {/* 비용 절감 팁 */}
          <div className="cost-tips">
            <h4>💡 비용 절감 팁</h4>
            <ul>
              <li>Gemini Flash, GPT-5 Mini 등 경량 모델 사용</li>
              <li>Google AI는 무료 사용량 제공</li>
              <li>OpenAI, Anthropic 신규 가입 시 $5 크레딧</li>
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

export default CostCalculator
