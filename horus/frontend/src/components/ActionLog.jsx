import React from "react";

export default function ActionLog({ actions }) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-hud-border text-xs text-hud-muted tracking-widest">
        ACTION LOG
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {actions.length === 0 && (
          <div className="text-hud-muted text-xs opacity-40 mt-4">No actions yet.</div>
        )}
        {actions.map((a, i) => (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span className="text-hud-accent mt-0.5">›</span>
            <span className={`text-hud-text ${i === 0 ? "text-hud-glow" : "opacity-60"}`}>
              {a.text}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
