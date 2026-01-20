/**
 * Simple markdown parser for AI messages
 * Handles: bold, italic, code, lists, line breaks
 */
function parseMarkdown(text) {
  if (!text) return ''

  // Escape HTML first
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // Code blocks (```)
  html = html.replace(/```([\s\S]*?)```/g, '<pre class="code-block">$1</pre>')

  // Inline code (`)
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')

  // Bold (**text**)
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')

  // Italic (*text*)
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')

  // Headers (### text)
  html = html.replace(/^### (.+)$/gm, '<h4 class="md-h4">$1</h4>')
  html = html.replace(/^## (.+)$/gm, '<h3 class="md-h3">$1</h3>')
  html = html.replace(/^# (.+)$/gm, '<h2 class="md-h2">$1</h2>')

  // Unordered lists (- item or * item)
  html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul class="md-list">$&</ul>')

  // Numbered lists (1. item)
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>')

  // Line breaks
  html = html.replace(/\n/g, '<br/>')

  // Clean up extra breaks inside lists
  html = html.replace(/<\/li><br\/>/g, '</li>')
  html = html.replace(/<br\/><li>/g, '<li>')

  return html
}

// SVG Icons
const Icons = {
  User: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  ),
  Paperclip: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  ),
  AlertCircle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
  Clock: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  )
}

function AgentMessage({ message }) {
  const { agent, content, isUser, isError, isStreaming, isInitialTopic, hasFiles, isPending } = message

  if (isUser) {
    return (
      <div className={`message user-message ${isInitialTopic ? 'initial-topic' : ''} ${isPending ? 'pending' : ''}`}>
        <div className="message-header">
          <span className="user-avatar">
            <Icons.User />
          </span>
          <span className="sender-name">{isInitialTopic ? '주제' : '사용자'}</span>
          {isPending && (
            <span className="pending-badge">
              <Icons.Clock />
              대기 중
            </span>
          )}
        </div>
        <div className="message-content user-content">
          {content}
          {hasFiles && (
            <span className="file-indicator">
              <Icons.Paperclip />
            </span>
          )}
        </div>
        {isPending && (
          <div className="pending-indicator">
            <span>AI 응답 후 반영됩니다</span>
          </div>
        )}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="message error-message">
        <div className="message-header error-header">
          <span className="error-avatar">
            <Icons.AlertCircle />
          </span>
          <span className="sender-name">시스템</span>
        </div>
        <div className="message-content error-content">
          {content}
        </div>
      </div>
    )
  }

  if (!agent) return null

  // Apply markdown parsing to completed messages, plain text for streaming
  const renderedContent = isStreaming
    ? content
    : parseMarkdown(content)

  return (
    <div className="message agent-message">
      <div
        className="message-header"
        style={{ '--agent-color': agent.color }}
      >
        <span
          className="agent-avatar"
          style={{ backgroundColor: agent.color }}
        >
          {agent.name?.charAt(0) || 'A'}
        </span>
        <div className="agent-info">
          <span className="sender-name">{agent.name}</span>
          <span className="sender-model">{agent.model}</span>
        </div>
        {isStreaming && <span className="streaming-badge">입력 중</span>}
      </div>
      <div className="message-content agent-content">
        {isStreaming ? (
          <>
            {content}
            <span className="cursor-blink">|</span>
          </>
        ) : (
          <div
            className="markdown-content"
            dangerouslySetInnerHTML={{ __html: renderedContent }}
          />
        )}
      </div>
    </div>
  )
}

export default AgentMessage
