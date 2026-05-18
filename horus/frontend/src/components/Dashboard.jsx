import React, { useState } from "react";
import StatusBar from "./StatusBar";
import ConversationFeed from "./ConversationFeed";
import ActionLog from "./ActionLog";
import MemoryPanel from "./MemoryPanel";
import ConfirmModal from "./ConfirmModal";
import SettingsPanel from "./SettingsPanel";
import QuickActions from "./QuickActions";
import NeuralSphere from "./NeuralSphere";

export default function Dashboard({
  messages, status, actions, memories, pendingConfirm, settings,
  onSendText, onVoiceStart, onConfirmApprove, onConfirmDeny,
  onUpdateSettings, onClearMemory,
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const busy = status !== "idle";

  return (
    <div className="min-h-screen bg-hud-bg text-hud-text font-mono flex flex-col">
      <ConfirmModal
        description={pendingConfirm}
        onApprove={onConfirmApprove}
        onDeny={onConfirmDeny}
      />

      <SettingsPanel
        open={settingsOpen}
        settings={settings}
        onUpdateSettings={onUpdateSettings}
        onClearMemory={() => { onClearMemory(); setSettingsOpen(false); }}
        onClose={() => setSettingsOpen(false)}
      />

      {/* Top bar */}
      <header className="border-b border-hud-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-hud-accent/20 border border-hud-accent flex items-center justify-center shadow-glow">
            <span className="text-hud-glow text-sm font-bold">H</span>
          </div>
          <span className="text-hud-glow font-bold tracking-widest text-lg">HORUS</span>
          <span className="text-hud-muted text-xs tracking-wider">/ AGENTIC ASSISTANT</span>
        </div>

        <div className="flex items-center gap-4">
          {settings.wake_word_enabled && (
            <span className="text-xs text-hud-success tracking-widest animate-pulse">
              ● WAKE WORD ACTIVE
            </span>
          )}
          {!settings.computer_use_enabled && (
            <span className="text-xs text-hud-danger tracking-widest">
              COMPUTER USE OFF
            </span>
          )}
          <StatusBar status={status} />
          <button
            onClick={() => setSettingsOpen(true)}
            className="text-hud-muted hover:text-hud-accent text-xs tracking-widest border border-hud-border hover:border-hud-accent px-3 py-1 rounded transition-all"
          >
            SETTINGS
          </button>
        </div>
      </header>

      {/* Quick actions */}
      <QuickActions onSendText={onSendText} disabled={busy} />

      {/* Main grid — 3 columns */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left: conversation */}
        <div className="w-80 flex flex-col border-r border-hud-border flex-shrink-0">
          <ConversationFeed
            messages={messages}
            onSendText={onSendText}
            onVoiceStart={onVoiceStart}
            status={status}
          />
        </div>

        {/* Center: neural sphere */}
        <div className="flex-1 flex flex-col items-center justify-center bg-hud-bg relative overflow-hidden">
          <div className="w-full h-full">
            <NeuralSphere status={status} />
          </div>
          {/* Status label below sphere */}
          <div className="absolute bottom-4 left-0 right-0 flex justify-center">
            <span className="text-xs tracking-widest text-hud-muted uppercase">
              {status === "idle" ? "STANDBY" : status.toUpperCase()}
            </span>
          </div>
        </div>

        {/* Right: action log + memory */}
        <div className="w-80 flex flex-col border-l border-hud-border flex-shrink-0">
          <div className="flex-1 border-b border-hud-border overflow-hidden">
            <ActionLog actions={actions} />
          </div>
          <div className="flex-1 overflow-hidden">
            <MemoryPanel memories={memories} />
          </div>
        </div>

      </div>
    </div>
  );
}
