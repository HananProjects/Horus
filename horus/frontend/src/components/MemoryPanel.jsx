import React from "react";

export default function MemoryPanel({ memories }) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-hud-border text-xs text-hud-muted tracking-widest">
        MEMORY
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {memories.length === 0 && (
          <div className="text-hud-muted text-xs opacity-40 mt-4">No memories stored yet.</div>
        )}
        {memories.map((m, i) => (
          <div
            key={i}
            className="text-xs text-hud-text bg-hud-panel border border-hud-border rounded px-3 py-2 leading-relaxed opacity-80 hover:opacity-100 transition-opacity"
          >
            {m}
          </div>
        ))}
      </div>
    </div>
  );
}
