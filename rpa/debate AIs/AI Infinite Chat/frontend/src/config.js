/**
 * AI Infinite Chat - Configuration
 * 중앙화된 설정 관리
 */

// API URLs - Docker 환경에서는 Nginx가 프록시하므로 상대 경로 사용
const getApiBaseUrl = () => {
  // 환경변수가 설정되어 있으면 사용
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL
  }
  // 개발 환경 (localhost:5173에서 실행)
  if (window.location.hostname === 'localhost' && window.location.port === '5173') {
    return 'http://localhost:8000'
  }
  // 프로덕션 환경 (Nginx 프록시) - 빈 문자열 = 현재 호스트
  return ''
}

const getWsUrl = () => {
  // 환경변수가 설정되어 있으면 사용
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL
  }
  // 개발 환경 (localhost:5173에서 실행)
  if (window.location.hostname === 'localhost' && window.location.port === '5173') {
    return 'ws://localhost:8000/ws/chat'
  }
  // 프로덕션 환경 - 현재 호스트 기반으로 동적 생성
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}/ws/chat`
}

export const API_BASE_URL = getApiBaseUrl()
export const WS_URL = getWsUrl()

// API 제공자 정보
export const PROVIDERS = {
  openai: {
    name: 'OpenAI',
    keyPrefix: 'sk-',
    signupUrl: 'https://platform.openai.com/signup',
    apiKeyUrl: 'https://platform.openai.com/api-keys',
    pricingUrl: 'https://openai.com/pricing',
    docsUrl: 'https://platform.openai.com/docs',
    description: '신규 가입 시 $5 무료 크레딧',
    color: '#10a37f'
  },
  google: {
    name: 'Google AI',
    keyPrefix: 'AI',
    signupUrl: 'https://aistudio.google.com/',
    apiKeyUrl: 'https://aistudio.google.com/app/apikey',
    pricingUrl: 'https://ai.google.dev/pricing',
    docsUrl: 'https://ai.google.dev/docs',
    description: '무료 사용량 제공',
    color: '#4285f4'
  },
  anthropic: {
    name: 'Anthropic',
    keyPrefix: 'sk-ant-',
    signupUrl: 'https://console.anthropic.com/',
    apiKeyUrl: 'https://console.anthropic.com/settings/keys',
    pricingUrl: 'https://www.anthropic.com/pricing',
    docsUrl: 'https://docs.anthropic.com/',
    description: '신규 가입 시 $5 무료 크레딧',
    color: '#d97706'
  },
  xai: {
    name: 'xAI',
    keyPrefix: 'xai-',
    signupUrl: 'https://console.x.ai/',
    apiKeyUrl: 'https://console.x.ai/api-keys',
    pricingUrl: 'https://x.ai/pricing',
    docsUrl: 'https://docs.x.ai/',
    description: '무료 티어 제공',
    color: '#000000'
  }
}

// 모델별 가격 정보 (USD per 1M tokens)
// avgOutputTokens: 평균 출력 토큰 수
// avgInputBase: 기본 입력 토큰 수 (프롬프트 + 시스템 메시지)
export const MODEL_PRICING = {
  'gpt-5-mini': {
    input: 0.15,
    output: 0.60,
    avgOutputTokens: 400,
    avgInputBase: 200,
    contextWindow: 128000
  },
  'gpt-5.2': {
    input: 2.50,
    output: 10.00,
    avgOutputTokens: 600,
    avgInputBase: 200,
    contextWindow: 128000
  },
  'gemini-3-flash-preview': {
    input: 0.075,
    output: 0.30,
    avgOutputTokens: 400,
    avgInputBase: 200,
    contextWindow: 1000000
  },
  'gemini-3-pro-preview': {
    input: 1.25,
    output: 5.00,
    avgOutputTokens: 500,
    avgInputBase: 200,
    contextWindow: 2000000
  },
  'claude-3-haiku': {
    input: 0.25,
    output: 1.25,
    avgOutputTokens: 400,
    avgInputBase: 200,
    contextWindow: 200000
  },
  'claude-3-sonnet': {
    input: 3.00,
    output: 15.00,
    avgOutputTokens: 600,
    avgInputBase: 200,
    contextWindow: 200000
  },
  'grok-beta': {
    input: 5.00,
    output: 15.00,
    avgOutputTokens: 500,
    avgInputBase: 200,
    contextWindow: 131072
  },
}

// 사용 가능한 모델 목록
export const AVAILABLE_MODELS = [
  {
    id: 'gpt-5-mini',
    name: 'GPT-5 Mini',
    provider: 'openai',
    speed: 'fast',
    description: '빠른 응답, 경제적',
    costTier: 'low'
  },
  {
    id: 'gpt-5.2',
    name: 'GPT-5.2',
    provider: 'openai',
    speed: 'normal',
    description: '높은 품질, 복잡한 작업',
    costTier: 'high'
  },
  {
    id: 'gemini-3-flash-preview',
    name: 'Gemini 3 Flash',
    provider: 'google',
    speed: 'fast',
    description: '빠른 응답, 무료 사용량',
    costTier: 'low'
  },
  {
    id: 'gemini-3-pro-preview',
    name: 'Gemini 3 Pro',
    provider: 'google',
    speed: 'normal',
    description: '높은 품질, 긴 컨텍스트',
    costTier: 'medium'
  },
]

// 속도 옵션
export const SPEED_OPTIONS = [
  { value: 'very_fast', label: '매우 빠름', description: '즉시 응답' },
  { value: 'fast', label: '빠름', description: '0.8초 간격' },
  { value: 'normal', label: '보통', description: '1.5초 간격' },
  { value: 'slow', label: '느림', description: '타이핑 효과' },
  { value: 'very_slow', label: '매우 느림', description: '실제 타이핑' },
]

// 주제 예시
export const TOPIC_EXAMPLES = [
  '인공지능이 인류의 미래에 미칠 영향',
  '기후 변화 대응을 위한 효과적인 방법',
  '원격 근무 vs 사무실 근무의 효율성',
  '소셜 미디어가 사회에 미치는 영향',
  '교육 시스템의 개혁 방향',
]

// 에이전트 색상 팔레트
export const AGENT_COLORS = [
  '#2563eb', // Blue
  '#7c3aed', // Purple
  '#059669', // Emerald
  '#ea580c', // Orange
  '#db2777', // Pink
]

// 에러 메시지 매핑
export const ERROR_MESSAGES = {
  'api key': 'API 키가 유효하지 않습니다. 설정에서 확인해주세요.',
  'timeout': 'AI 응답 시간이 초과되었습니다. 다시 시도해주세요.',
  'rate limit': '요청 제한에 도달했습니다. 잠시 후 다시 시도해주세요.',
  'network': '네트워크 연결을 확인해주세요.',
  'default': '일시적인 오류가 발생했습니다. 다시 시도해주세요.'
}

// 에러 메시지 변환
export const getUserFriendlyError = (errorContent) => {
  if (!errorContent) return ERROR_MESSAGES.default

  const errorStr = String(errorContent).toLowerCase()

  for (const [key, message] of Object.entries(ERROR_MESSAGES)) {
    if (key !== 'default' && errorStr.includes(key)) {
      return message
    }
  }

  return ERROR_MESSAGES.default
}

// 비용 계산
export const calculateCost = (inputTokens, outputTokens, modelId) => {
  const pricing = MODEL_PRICING[modelId]
  if (!pricing) return 0

  const inputCost = (inputTokens * pricing.input) / 1_000_000
  const outputCost = (outputTokens * pricing.output) / 1_000_000
  return inputCost + outputCost
}

// 비용 포맷팅
export const formatCost = (cost) => {
  if (cost === 0) return '$0.00'
  if (cost < 0.001) return '< $0.001'
  if (cost < 0.01) return `$${cost.toFixed(4)}`
  if (cost < 1) return `$${cost.toFixed(3)}`
  return `$${cost.toFixed(2)}`
}

// 원화 환산 (1달러 = 1,350원 기준)
export const formatKRW = (usdCost) => {
  const krwCost = usdCost * 1350
  if (krwCost < 1) return '< ₩1'
  return `₩${Math.round(krwCost).toLocaleString()}`
}

// 토큰 수 포맷팅
export const formatTokens = (tokens) => {
  if (tokens < 1000) return tokens.toString()
  if (tokens < 1000000) return `${(tokens / 1000).toFixed(1)}K`
  return `${(tokens / 1000000).toFixed(2)}M`
}

// 스토리지 키
export const STORAGE_KEYS = {
  API_KEYS: 'ai_chat_api_keys',
  FIRST_VISIT: 'ai_chat_first_visit',
  PREFERENCES: 'ai_chat_preferences',
  LAST_CONVERSATION: 'ai_chat_last_conversation'
}

// 안전 제한 설정
export const SAFETY_LIMITS = {
  // 최대 턴 수 (기본값)
  maxTurns: 100,
  // 최대 비용 (USD)
  maxCost: 1.00,
  // 최대 시간 (분)
  maxMinutes: 30,
  // 경고 임계값 (%)
  warningThreshold: 80,
  // 브라우저 비활성 시 자동 일시정지
  pauseOnInactive: true,
  // 비활성 감지 시간 (초)
  inactiveTimeout: 60
}

// 기본 설정
export const DEFAULT_CONFIG = {
  agentCount: 2,
  speed: 'normal',
  autoStart: true,
  models: [
    { id: 'gpt-5-mini', provider: 'openai' },
    { id: 'gemini-3-flash-preview', provider: 'google' }
  ],
  // 안전 제한
  limits: {
    maxTurns: SAFETY_LIMITS.maxTurns,
    maxCost: SAFETY_LIMITS.maxCost,
    maxMinutes: SAFETY_LIMITS.maxMinutes,
    pauseOnInactive: SAFETY_LIMITS.pauseOnInactive
  }
}
