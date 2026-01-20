import { useState, useRef } from 'react'
import { API_BASE_URL } from '../config'

// SVG Icons
const Icons = {
  Paperclip: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
    </svg>
  ),
  Send: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  ),
  X: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
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
  )
}

function UserInterventionBar({ onSend, disabled, placeholder }) {
  const [text, setText] = useState('')
  const [files, setFiles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const fileInputRef = useRef(null)

  const uploadFiles = async (fileList) => {
    if (fileList.length === 0) return []

    setUploading(true)
    setUploadError(null)
    try {
      const formData = new FormData()
      fileList.forEach(file => {
        formData.append('files', file)
      })

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
      setUploadError(`파일 업로드 실패: ${error.message}`)
      return []
    } finally {
      setUploading(false)
    }
  }

  const clearError = () => setUploadError(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if ((!text.trim() && files.length === 0) || disabled || uploading) return

    let uploadedFiles = []
    if (files.length > 0) {
      uploadedFiles = await uploadFiles(files)
    }

    onSend(text, uploadedFiles.map(f => f.id))
    setText('')
    setFiles([])
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleFileChange = (e) => {
    const newFiles = Array.from(e.target.files)
    setFiles(prev => [...prev, ...newFiles])
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

  return (
    <form className="intervention-bar" onSubmit={handleSubmit}>
      {uploadError && (
        <div className="upload-error">
          <span className="error-text">{uploadError}</span>
          <button type="button" className="btn-dismiss" onClick={clearError}>
            <Icons.X />
          </button>
        </div>
      )}

      {files.length > 0 && (
        <div className="attached-files">
          {files.map((file, index) => (
            <div key={index} className="file-chip">
              <span className="file-icon">
                {file.type.startsWith('image/') ? <Icons.Image /> : <Icons.File />}
              </span>
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatFileSize(file.size)}</span>
              <button
                type="button"
                className="file-remove"
                onClick={() => removeFile(index)}
                disabled={uploading}
              >
                <Icons.X />
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="input-row">
        <button
          type="button"
          className="btn-attach"
          onClick={() => fileInputRef.current?.click()}
          disabled={disabled || uploading}
          title="파일 첨부"
        >
          {uploading ? <Icons.Loader /> : <Icons.Paperclip />}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileChange}
          accept=".txt,.md,.csv,.json,.xml,.html,.css,.js,.py,.java,.cpp,.c,.h,.ts,.tsx,.jsx,.pdf,.doc,.docx,.jpg,.jpeg,.png,.gif,.webp,.svg"
          style={{ display: 'none' }}
        />

        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={uploading ? '파일 업로드 중...' : (placeholder || '대화에 참여하세요...')}
          disabled={disabled || uploading}
          className="intervention-input"
        />

        <button
          type="submit"
          className="btn-send"
          disabled={(!text.trim() && files.length === 0) || disabled || uploading}
          title="전송"
        >
          <Icons.Send />
        </button>
      </div>
    </form>
  )
}

export default UserInterventionBar
