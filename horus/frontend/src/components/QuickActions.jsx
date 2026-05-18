import React from "react";

const ACTIONS = [
  { label: "Open Spotify", text: "open Spotify" },
  { label: "Screenshot", text: "take a screenshot" },
  { label: "Search Google", text: "search Google for " },
  { label: "Open Terminal", text: "open Terminal" },
];

export default function QuickActions({ onSendText, disabled }) {
  return (
    <div className="flex gap-2 px-4 py-2 border-b border-hud-border flex-wrap">
      {ACTIONS.map((a) => (
        <button
          key={a.label}
          disabled={disabled}
          onClick={() => onSendText(a.text)}
          className="px-3 py-1 rounded border border-hud-border text-hud-muted text-xs tracking-wide hover:border-hud-accent hover:text-hud-accent transition-all disabled:opacity-30"
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}
