import React from "react";
import StatusBar from "./StatusBar";
import ConversationFeed from "./ConversationFeed";
import ActionLog from "./ActionLog";
import MemoryPanel from "./MemoryPanel";

export default function Dashboard({ messages, status, actions, memories, onSendText, onVoiceStart }) {
  return (
    <div className="min-h-screen bg-hud-bg text-hud-text font-mono flex flex-col">
      {/* Top bar */}
      <header className="border-b border-hud-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-hud-accent/20 border border-hud-accent flex items-center justify-center shadow-glow">
            <span className="text-hud-glow text-sm font-bold">H</span>
          </div>
          <span className="text-hud-glow font-bold tracking-widest text-lg">HORUS</span>
          <span className="text-hud-muted text-xs tracking-wider">/ AGENTIC ASSISTANT</span>
        </div>
        <StatusBar status={status} />
      </header>

      {/* Main grid */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Conversation */}
        <div className="flex-1 flex flex-col border-r border-hud-border">
          <ConversationFeed messages={messages} onSendText={onSendText} onVoiceStart={onVoiceStart} status={status} />
        </div>

        {/* Right: Action Log + Memory */}
        <div className="w-80 flex flex-col">
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
