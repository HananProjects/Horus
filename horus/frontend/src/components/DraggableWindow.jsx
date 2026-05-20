import { useState } from "react";

let _zCounter = 10;
function nextZ() { return ++_zCounter; }

export default function DraggableWindow({
  label,
  accentColor = "#00e5ff",
  defaultX = 0,
  defaultY = 0,
  defaultW = 272,
  defaultH = 300,
  minW = 160,
  minH = 80,
  baseZ = 10,
  onClose,
  children,
  style,
}) {
  const [pos, setPos] = useState({ x: defaultX, y: defaultY });
  const [size, setSize] = useState({ w: defaultW, h: defaultH });
  const [z, setZ] = useState(baseZ);

  function bringToFront() {
    setZ(nextZ());
  }

  function startDrag(e) {
    if (e.button !== 0) return;
    e.preventDefault();
    bringToFront();
    const ox = e.clientX - pos.x;
    const oy = e.clientY - pos.y;
    function move(ev) {
      setPos({ x: ev.clientX - ox, y: ev.clientY - oy });
    }
    function up() {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  function startResize(e) {
    if (e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();
    bringToFront();
    const sx = e.clientX, sy = e.clientY, sw = size.w, sh = size.h;
    function move(ev) {
      setSize({
        w: Math.max(minW, sw + ev.clientX - sx),
        h: Math.max(minH, sh + ev.clientY - sy),
      });
    }
    function up() {
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
    }
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  }

  return (
    <div
      onMouseDown={bringToFront}
      style={{
        position: "absolute",
        left: pos.x,
        top: pos.y,
        width: size.w,
        height: size.h,
        zIndex: z,
        display: "flex",
        flexDirection: "column",
        background: "rgba(5,10,15,0.87)",
        borderLeft: `1px solid ${accentColor}30`,
        borderTop: `1px solid ${accentColor}18`,
        borderRight: `1px solid ${accentColor}12`,
        borderBottom: `1px solid ${accentColor}10`,
        backdropFilter: "blur(6px)",
        overflow: "hidden",
        ...style,
      }}
    >
      {/* Left accent bar */}
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: 2, pointerEvents: "none",
        background: `linear-gradient(to bottom, ${accentColor}55, transparent)`,
      }} />

      {/* Header — drag handle */}
      <div
        onMouseDown={startDrag}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "5px 10px 5px 14px",
          borderBottom: `1px solid ${accentColor}15`,
          cursor: "move", userSelect: "none", flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 4, height: 4, borderRadius: "50%",
            background: accentColor, boxShadow: `0 0 6px ${accentColor}`, opacity: 0.9,
          }} />
          <span style={{ fontSize: "0.52rem", letterSpacing: "0.26em", color: accentColor, opacity: 0.9 }}>
            [ {label} ]
          </span>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            onMouseDown={e => e.stopPropagation()}
            style={{
              color: accentColor, opacity: 0.35, fontSize: "0.65rem",
              background: "none", border: "none", cursor: "pointer", lineHeight: 1, padding: "0 2px",
            }}
          >
            ✕
          </button>
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden", minHeight: 0 }}>
        {children}
      </div>

      {/* Resize grip */}
      <div
        onMouseDown={startResize}
        style={{
          position: "absolute", bottom: 0, right: 0,
          width: 16, height: 16, cursor: "se-resize",
          display: "flex", alignItems: "flex-end", justifyContent: "flex-end",
          padding: "3px",
        }}
      >
        <svg width="9" height="9" viewBox="0 0 9 9" style={{ pointerEvents: "none" }}>
          <line x1="2" y1="9" x2="9" y2="2" stroke={accentColor} strokeWidth="1" opacity="0.25" />
          <line x1="5" y1="9" x2="9" y2="5" stroke={accentColor} strokeWidth="1" opacity="0.25" />
        </svg>
      </div>
    </div>
  );
}
