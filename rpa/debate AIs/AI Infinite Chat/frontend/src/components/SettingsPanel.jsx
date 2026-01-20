function SettingsPanel({ apiKey, setApiKey, selectedModel, setSelectedModel, onClose }) {
  const models = [
    // OpenAI
    { id: 'gpt-5-mini', name: 'GPT-5 Mini (Fast)', provider: 'OpenAI' },
    { id: 'gpt-5.2', name: 'GPT-5.2', provider: 'OpenAI' },
    // Gemini
    { id: 'gemini-3-flash-preview', name: 'Gemini 3 Flash (Fast)', provider: 'Google' },
    { id: 'gemini-3-pro-preview', name: 'Gemini 3 Pro', provider: 'Google' },
  ]

  return (
    <div className="settings-panel">
      <h2>Settings</h2>

      <div className="setting-group">
        <label>OpenAI API Key</label>
        <input
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="sk-..."
        />
      </div>

      <div className="setting-group">
        <label>AI Model</label>
        <select
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
        >
          {models.map(model => (
            <option key={model.id} value={model.id}>
              [{model.provider}] {model.name}
            </option>
          ))}
        </select>
      </div>

      <button className="save-btn" onClick={onClose}>
        Save & Close
      </button>
    </div>
  )
}

export default SettingsPanel
