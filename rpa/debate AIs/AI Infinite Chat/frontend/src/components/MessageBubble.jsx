function MessageBubble({ message }) {
  const { role, content, model, isStreaming, isError } = message

  return (
    <div className={`message ${role} ${isError ? 'error' : ''}`}>
      {role === 'ai' && (
        <div className="message-sender">
          {model || 'AI'} {isStreaming && '...'}
        </div>
      )}
      <div className="message-content">
        {content}
        {isStreaming && <span className="cursor">|</span>}
      </div>
    </div>
  )
}

export default MessageBubble
