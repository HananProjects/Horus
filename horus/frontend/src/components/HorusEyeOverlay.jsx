import { useEffect, useRef, useState, useCallback } from "react";
import NeuralSphere from "./NeuralSphere";

const WS_URL = "ws://localhost:8000/ws";

// Inject keyframe + base styles once
const STYLE = `
  @keyframes horus-breathe {
    0%, 100% { transform: scale(1);    filter: brightness(1); }
    50%       { transform: scale(1.05); filter: brightness(1.15); }
  }
  @keyframes horus-pulse {
    0%, 100% { transform: scale(1);    filter: brightness(1); }
    50%       { transform: scale(1.08); filter: brightness(1.3); }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { background: transparent !important; overflow: hidden; user-select: none; }
`;

export default function HorusEyeOverlay() {
  const [status, setStatus] = useState("idle");
  const [hovered, setHovered] = useState(false);
  const wsRef = useRef(null);
  const dragRef = useRef(null);   // { startScreenX, startScreenY, startWinX, startWinY }

  // Inject CSS once
  useEffect(() => {
    const tag = document.createElement("style");
    tag.textContent = STYLE;
    document.head.appendChild(tag);
    return () => document.head.removeChild(tag);
  }, []);

  // WebSocket — listen for status only
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          if (d.type === "status") setStatus(d.status);
        } catch {}
      };
      ws.onclose = () => setTimeout(connect, 2000);
    }
    connect();
    return () => {
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }
    };
  }, []);

  // Tell main process whether the eye should accept mouse events
  useEffect(() => {
    window.electronAPI?.setClickable(hovered);
  }, [hovered]);

  // Drag: on mousedown record start position, on mousemove send delta
  const onMouseDown = useCallback(async (e) => {
    if (!window.electronAPI) return;
    const [wx, wy] = await window.electronAPI.getOverlayPos();
    dragRef.current = {
      startScreenX: e.screenX,
      startScreenY: e.screenY,
      startWinX: wx,
      startWinY: wy,
    };

    function onMove(ev) {
      if (!dragRef.current) return;
      const dx = ev.screenX - dragRef.current.startScreenX;
      const dy = ev.screenY - dragRef.current.startScreenY;
      window.electronAPI.moveOverlay(
        dragRef.current.startWinX + dx,
        dragRef.current.startWinY + dy
      );
    }
    function onUp() {
      dragRef.current = null;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, []);

  const idle     = status === "idle";
  const speaking = status === "speaking";
  const thinking = status === "thinking" || status === "processing";
  const active   = !idle;

  // Overall opacity: ghostly when idle, vivid when active
  const opacity = hovered ? 0.95 : idle ? 0.18 : speaking ? 0.9 : thinking ? 0.75 : 0.6;

  // Glow intensity
  const glowA  = idle ? 0.06 : speaking ? 0.55 : 0.35;
  const ringA  = idle ? 0.12 : speaking ? 0.6  : 0.4;

  // Breathing animation
  const animation = idle
    ? "horus-breathe 4s ease-in-out infinite"
    : speaking
    ? "horus-pulse 0.9s ease-in-out infinite"
    : "horus-breathe 2s ease-in-out infinite";

  return (
    <div style={{
      width: "100vw",
      height: "100vh",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      background: "transparent",
    }}>
      {/* Draggable + hoverable wrapper */}
      <div
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onMouseDown={onMouseDown}
        onClick={() => window.electronAPI?.openFullUI()}
        style={{
          width: 160,
          height: 160,
          position: "relative",
          cursor: hovered ? "pointer" : "default",
          opacity,
          transition: "opacity 1.4s ease",
          animation,
        }}
      >
        {/* Outer ambient glow */}
        <div style={{
          position: "absolute",
          inset: -16,
          borderRadius: "50%",
          background: `radial-gradient(circle, rgba(245,158,11,${glowA}) 0%, transparent 65%)`,
          pointerEvents: "none",
          transition: "background 1s ease",
        }} />

        {/* Eye circle */}
        <div style={{
          width: "100%",
          height: "100%",
          borderRadius: "50%",
          overflow: "hidden",
          border: `1px solid rgba(245,158,11,${ringA})`,
          background: "radial-gradient(circle, rgba(12,9,4,0.7) 0%, rgba(0,0,0,0.88) 100%)",
          boxShadow: `0 0 ${active ? 32 : 14}px rgba(245,158,11,${glowA}), inset 0 0 12px rgba(245,158,11,0.04)`,
          transition: "all 1s ease",
        }}>
          <NeuralSphere status={status} nodeCount={0} />
        </div>

        {/* Hover label */}
        {hovered && (
          <div style={{
            position: "absolute",
            bottom: -26,
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: 10,
            color: "rgba(245,158,11,0.7)",
            letterSpacing: "0.12em",
            whiteSpace: "nowrap",
            fontFamily: "monospace",
          }}>
            OPEN HORUS
          </div>
        )}
      </div>
    </div>
  );
}
