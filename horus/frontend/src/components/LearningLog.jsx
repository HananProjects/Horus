import React from "react";

export default function LearningLog({ updates, onClear }) {
  if (!updates || updates.length === 0) return null;

  const totalDiscoveries = updates.reduce((n, u) => n + u.discoveries.length, 0);

  return (
    <div className="border-t border-hud-accent/30 bg-hud-accent/5 flex flex-col overflow-hidden" style={{ maxHeight: "160px" }}>
      <div className="flex items-center justify-between px-4 py-1.5 border-b border-hud-accent/20">
        <span className="text-hud-accent text-xs tracking-widest font-bold">
          ● HORUS LEARNED &mdash; {totalDiscoveries} DISCOVERIES
        </span>
        <button
          onClick={onClear}
          className="text-hud-muted hover:text-hud-accent text-xs tracking-widest transition-colors"
        >
          DISMISS
        </button>
      </div>
      <div className="overflow-y-auto flex-1 px-4 py-2 space-y-1">
        {updates.flatMap((update) =>
          update.discoveries.map((d, i) => (
            <div key={`${update.ts}-${i}`} className="text-xs text-hud-muted leading-relaxed">
              <span className="text-hud-accent/60 mr-2">›</span>{d}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
