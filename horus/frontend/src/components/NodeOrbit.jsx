import { useState, useEffect, useRef } from "react";

function seededRand(seed) {
  let s = Math.abs(seed * 16807 + 7) % 2147483647;
  s = (s * 16807) % 2147483647;
  return (s - 1) / 2147483646;
}

function naturalPos(nodeId, cx, cy, r) {
  const stored = localStorage.getItem(`horus_node_${nodeId}`);
  if (stored) { try { return JSON.parse(stored); } catch {} }
  const angle = seededRand(nodeId * 5 + 1) * Math.PI * 2;
  const dist = r * (0.68 + seededRand(nodeId * 11 + 3) * 0.52);
  return { x: cx + Math.cos(angle) * dist, y: cy + Math.sin(angle) * dist };
}

const NODE_ACTIONS = {
  pdf:     ["open", "summarize", "read_aloud", "remove"],
  url:     ["open", "summarize", "remove"],
  website: ["open", "summarize", "remove"],
  image:   ["open", "remove"],
  file:    ["open", "remove"],
  app:     ["launch", "remove"],
  task:    ["complete", "remove"],
  note:    ["read_aloud", "remove"],
  music:   ["play", "remove"],
  audio:   ["play", "remove"],
  search:  ["search_again", "open", "remove"],
  generic: ["remove"],
};

const ACTION_LABELS = {
  open:         "Open",
  summarize:    "Summarize",
  read_aloud:   "Read Aloud",
  launch:       "Launch",
  complete:     "Mark Complete",
  play:         "Play",
  search_again: "Search Again",
  remove:       "Remove",
};

const ACTION_DANGER = new Set(["remove", "complete"]);

function getActions(nodeType) {
  return NODE_ACTIONS[nodeType] || NODE_ACTIONS.generic;
}

export default function NodeOrbit({ nodes, onRemove, onNodeAction }) {
  const [dims, setDims] = useState({ w: window.innerWidth, h: window.innerHeight });
  const [positions, setPositions] = useState({});
  const [floats, setFloats] = useState({});
  const [contextMenu, setContextMenu] = useState(null); // { node, x, y }
  const clock = useRef(0);
  const drag = useRef(null);
  const didDrag = useRef(false);
  const menuRef = useRef(null);

  useEffect(() => {
    const h = () => setDims({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener("resize", h);
    return () => window.removeEventListener("resize", h);
  }, []);

  // Close context menu on outside click or Escape
  useEffect(() => {
    if (!contextMenu) return;
    const handleClick = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setContextMenu(null);
      }
    };
    const handleKey = (e) => { if (e.key === "Escape") setContextMenu(null); };
    window.addEventListener("mousedown", handleClick);
    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("mousedown", handleClick);
      window.removeEventListener("keydown", handleKey);
    };
  }, [contextMenu]);

  const cx = dims.w / 2;
  const cy = dims.h / 2;
  const baseR = Math.min(dims.w, dims.h) * 0.38;

  const nodeKey = nodes.map(n => n.id).join(",");
  useEffect(() => {
    setPositions(prev => {
      const next = {};
      nodes.forEach(n => {
        next[n.id] = prev[n.id] ?? naturalPos(n.id, cx, cy, baseR);
      });
      return next;
    });
  }, [nodeKey, cx, cy, baseR]); // eslint-disable-line

  useEffect(() => {
    let raf;
    const tick = () => {
      clock.current += 0.012;
      const t = clock.current;
      const f = {};
      nodes.forEach(n => {
        const ph = seededRand(n.id * 3 + 2) * Math.PI * 2;
        const sp = 0.3 + seededRand(n.id * 7 + 1) * 0.25;
        f[n.id] = {
          x: Math.sin(t * sp * 0.55 + ph + 1.2) * 5,
          y: Math.sin(t * sp + ph) * 7,
        };
      });
      setFloats(f);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [nodeKey]); // eslint-disable-line

  useEffect(() => {
    const onMove = (e) => {
      if (!drag.current) return;
      const { nodeId, ox, oy, mx, my } = drag.current;
      const dx = e.clientX - mx;
      const dy = e.clientY - my;
      if (Math.hypot(dx, dy) > 5) didDrag.current = true;
      setPositions(prev => ({ ...prev, [nodeId]: { x: ox + dx, y: oy + dy } }));
    };
    const onUp = () => {
      if (!drag.current) return;
      const { nodeId } = drag.current;
      setPositions(prev => {
        if (prev[nodeId]) localStorage.setItem(`horus_node_${nodeId}`, JSON.stringify(prev[nodeId]));
        return prev;
      });
      drag.current = null;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  function handleAction(node, action) {
    setContextMenu(null);
    if (action === "remove") {
      onRemove(node.id);
    } else {
      onNodeAction(node.id, action);
    }
  }

  if (!nodes.length) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-10">
      <svg className="absolute inset-0 w-full h-full">
        {nodes.map(n => {
          const pos = positions[n.id];
          if (!pos) return null;
          const isDragging = drag.current?.nodeId === n.id;
          const f = floats[n.id] ?? { x: 0, y: 0 };
          const vx = isDragging ? pos.x : pos.x + f.x;
          const vy = isDragging ? pos.y : pos.y + f.y;
          return (
            <line key={n.id}
              x1={cx} y1={cy} x2={vx} y2={vy}
              stroke="#f59e0b" strokeOpacity="0.18" strokeWidth="1" strokeDasharray="4 8"
            />
          );
        })}
      </svg>

      {nodes.map(n => {
        const pos = positions[n.id];
        if (!pos) return null;
        const isDragging = drag.current?.nodeId === n.id;
        const f = floats[n.id] ?? { x: 0, y: 0 };
        const vx = isDragging ? pos.x : pos.x + f.x;
        const vy = isDragging ? pos.y : pos.y + f.y;

        return (
          <div key={n.id}
            className="absolute flex flex-col items-center gap-1.5 pointer-events-auto group select-none"
            style={{
              left: vx, top: vy,
              transform: "translate(-50%, -50%)",
              cursor: isDragging ? "grabbing" : "grab",
            }}
            onMouseDown={e => {
              if (e.button !== 0) return;
              didDrag.current = false;
              drag.current = { nodeId: n.id, ox: pos.x, oy: pos.y, mx: e.clientX, my: e.clientY };
            }}
            onClick={() => {
              if (!didDrag.current) onRemove(n.id);
              didDrag.current = false;
            }}
            onContextMenu={e => {
              e.preventDefault();
              e.stopPropagation();
              setContextMenu({ node: n, x: e.clientX, y: e.clientY });
            }}
          >
            <div className="relative flex items-center justify-center">
              <div className="absolute w-6 h-6 rounded-full bg-amber-400/10 animate-pulse" />
              <div className="w-2 h-2 rounded-full bg-amber-400 group-hover:bg-red-400 transition-colors"
                style={{ boxShadow: "0 0 8px rgba(245,158,11,0.9)" }} />
            </div>
            <span className="text-amber-300/60 whitespace-nowrap group-hover:text-red-400/60 transition-colors"
              style={{ fontSize: "0.58rem", letterSpacing: "0.15em", textTransform: "uppercase" }}>
              {n.label}
            </span>
          </div>
        );
      })}

      {/* Context menu */}
      {contextMenu && (
        <div
          ref={menuRef}
          className="absolute pointer-events-auto z-50"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          <div
            className="flex flex-col py-1 min-w-[140px]"
            style={{
              background: "rgba(10,8,4,0.92)",
              border: "1px solid rgba(245,158,11,0.25)",
              boxShadow: "0 0 24px rgba(245,158,11,0.08), 0 4px 24px rgba(0,0,0,0.7)",
            }}
          >
            <div
              className="px-3 py-1.5 mb-1"
              style={{
                borderBottom: "1px solid rgba(245,158,11,0.12)",
                fontSize: "0.52rem",
                letterSpacing: "0.2em",
                color: "rgba(245,158,11,0.4)",
                textTransform: "uppercase",
              }}
            >
              {contextMenu.node.label}
            </div>
            {getActions(contextMenu.node.type || "generic").map(action => (
              <button
                key={action}
                className="text-left px-3 py-1.5 transition-colors"
                style={{
                  fontSize: "0.65rem",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: ACTION_DANGER.has(action)
                    ? "rgba(248,113,113,0.7)"
                    : "rgba(245,158,11,0.75)",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: "100%",
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = "rgba(245,158,11,0.06)";
                  e.currentTarget.style.color = ACTION_DANGER.has(action)
                    ? "rgba(248,113,113,1)"
                    : "rgba(245,158,11,1)";
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = ACTION_DANGER.has(action)
                    ? "rgba(248,113,113,0.7)"
                    : "rgba(245,158,11,0.75)";
                }}
                onClick={() => handleAction(contextMenu.node, action)}
              >
                {ACTION_LABELS[action] || action}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
