import React from "react";

const STATUS_CONFIG = {
  idle:      { label: "IDLE",      color: "text-hud-muted",   dot: "bg-hud-muted" },
  listening: { label: "LISTENING", color: "text-hud-success",  dot: "bg-hud-success animate-pulse" },
  thinking:  { label: "THINKING",  color: "text-hud-accent",   dot: "bg-hud-accent animate-pulse" },
  speaking:  { label: "SPEAKING",  color: "text-hud-glow",     dot: "bg-hud-glow animate-pulse-glow" },
};

export default function StatusBar({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.idle;
  return (
    <div className="flex items-center gap-2">
      <div className={`w-2 h-2 rounded-full ${cfg.dot}`} />
      <span className={`text-xs tracking-widest ${cfg.color}`}>{cfg.label}</span>
    </div>
  );
}
