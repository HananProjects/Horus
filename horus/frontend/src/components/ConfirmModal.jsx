import React from "react";

export default function ConfirmModal({ description, onApprove, onDeny }) {
  if (!description) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="bg-hud-panel border border-hud-accent rounded-lg shadow-glow-lg w-full max-w-md mx-4 p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-2 h-2 rounded-full bg-hud-accent animate-pulse" />
          <span className="text-xs text-hud-muted tracking-widest">COMPUTER USE — CONFIRMATION REQUIRED</span>
        </div>

        <p className="text-hud-text text-sm leading-relaxed mb-6">
          {description}
        </p>

        <div className="flex gap-3">
          <button
            onClick={onApprove}
            className="flex-1 py-2 rounded border border-hud-success text-hud-success text-xs tracking-widest hover:bg-hud-success/10 transition-all"
          >
            APPROVE
          </button>
          <button
            onClick={onDeny}
            className="flex-1 py-2 rounded border border-hud-danger text-hud-danger text-xs tracking-widest hover:bg-hud-danger/10 transition-all"
          >
            DENY
          </button>
        </div>
      </div>
    </div>
  );
}
