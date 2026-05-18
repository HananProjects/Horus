import React from "react";

function Toggle({ label, description, value, onChange }) {
  return (
    <div className="flex items-start justify-between gap-4 py-3 border-b border-hud-border last:border-0">
      <div>
        <div className="text-xs text-hud-text tracking-wide">{label}</div>
        {description && <div className="text-xs text-hud-muted mt-0.5">{description}</div>}
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`flex-shrink-0 w-10 h-5 rounded-full border transition-all ${
          value
            ? "bg-hud-accent/20 border-hud-accent"
            : "bg-transparent border-hud-muted"
        }`}
      >
        <div
          className={`w-3 h-3 rounded-full mx-auto transition-all ${
            value ? "bg-hud-glow translate-x-2.5" : "bg-hud-muted -translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

export default function SettingsPanel({ open, settings, onUpdateSettings, onClearMemory, onClose }) {
  if (!open) return null;

  function update(key, value) {
    onUpdateSettings({ ...settings, [key]: value });
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative w-80 bg-hud-panel border-l border-hud-border h-full flex flex-col shadow-glow-lg">
        <div className="flex items-center justify-between px-4 py-3 border-b border-hud-border">
          <span className="text-xs text-hud-muted tracking-widest">SETTINGS</span>
          <button
            onClick={onClose}
            className="text-hud-muted hover:text-hud-text text-xs"
          >
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4">
          <div className="text-xs text-hud-muted tracking-widest mb-3">CAPABILITIES</div>

          <Toggle
            label="Computer Use"
            description="Allow Horus to control your screen"
            value={settings.computer_use_enabled ?? true}
            onChange={(v) => update("computer_use_enabled", v)}
          />
          <Toggle
            label="Wake Word"
            description={'Listen for "Horus" to activate'}
            value={settings.wake_word_enabled ?? false}
            onChange={(v) => update("wake_word_enabled", v)}
          />

          <div className="mt-6 text-xs text-hud-muted tracking-widest mb-3">VOICE</div>
          <div className="py-3">
            <div className="flex justify-between text-xs mb-2">
              <span className="text-hud-text">Speed</span>
              <span className="text-hud-accent">{settings.voice_rate ?? 185}</span>
            </div>
            <input
              type="range"
              min={120}
              max={280}
              value={settings.voice_rate ?? 185}
              onChange={(e) => update("voice_rate", Number(e.target.value))}
              className="w-full accent-hud-accent"
            />
            <div className="flex justify-between text-xs text-hud-muted mt-1">
              <span>Slow</span>
              <span>Fast</span>
            </div>
          </div>

          <div className="mt-6 text-xs text-hud-muted tracking-widest mb-3">MEMORY</div>
          <button
            onClick={onClearMemory}
            className="w-full py-2 rounded border border-hud-danger text-hud-danger text-xs tracking-wider hover:bg-hud-danger/10 transition-all"
          >
            CLEAR ALL MEMORY
          </button>
          <p className="text-xs text-hud-muted mt-2">
            Permanently deletes all stored conversation memory from ChromaDB.
          </p>
        </div>
      </div>
    </div>
  );
}
