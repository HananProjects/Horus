import { useState, useEffect } from "react";
import DraggableWindow from "./DraggableWindow";
import GlobeViewer from "./GlobeViewer";

// --- Agent result panels ---

const AGENT_CONFIG = {
  research: { label: "RESEARCH", color: "#00e5ff" },
  code:     { label: "CODE",     color: "#06d6a0" },
  task:     { label: "TASK",     color: "#f59e0b" },
};

const VISUAL_CONFIG = {
  stock:   { label: "LIVE CHART", color: "#00e5ff", defaultW: 300, defaultH: 220 },
  image:   { label: "IMAGE",      color: "#f59e0b", defaultW: 320, defaultH: 300 },
  video:   { label: "VIDEO",      color: "#ef233c", defaultW: 400, defaultH: 260 },
  webpage: { label: "PREVIEW",    color: "#06d6a0", defaultW: 420, defaultH: 340 },
  score:   { label: "LIVE SCORE", color: "#ef233c", defaultW: 340, defaultH: 210 },
  card:    { label: "INFO CARD",  color: "#f59e0b", defaultW: 360, defaultH: 420 },
  map:     { label: "MAP",        color: "#22c55e", defaultW: 480, defaultH: 360 },
};

// --- Sparkline for stock ---

function Sparkline({ closes, isPositive }) {
  if (!closes || closes.length < 2) return null;
  const W = 280, H = 58;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const rng = max - min || 1;
  const pts = closes.map((v, i) => ({
    x: (i / (closes.length - 1)) * W,
    y: H - ((v - min) / rng) * (H - 8) - 4,
  }));
  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const area = line + ` L${W},${H} L0,${H} Z`;
  const color = isPositive ? "#06d6a0" : "#ef233c";
  const gid = `spk_${isPositive ? "up" : "dn"}`;

  return (
    <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: "block" }} preserveAspectRatio="none">
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.18" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gid})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="1.5" opacity="0.9" />
    </svg>
  );
}

// --- Stock content ---

function StockContent({ panel }) {
  const d = panel.data || {};
  if (d.error) return (
    <div style={{ padding: "12px 14px", fontSize: "0.6rem", color: "#ef233c", opacity: 0.8 }}>
      Could not load data: {d.error}
    </div>
  );
  const isPos = (d.change ?? 0) >= 0;
  const changeColor = isPos ? "#06d6a0" : "#ef233c";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ padding: "10px 14px 0" }}>
        {/* Ticker row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <span style={{ fontSize: "0.6rem", letterSpacing: "0.22em", color: "#00b4d8", opacity: 0.8 }}>
            {panel.symbol}
          </span>
          <span style={{ fontSize: "0.44rem", letterSpacing: "0.1em", color: "rgba(90,143,163,0.55)" }}>
            {d.exchange} · {d.currency}
          </span>
        </div>
        {/* Price */}
        <div style={{ fontSize: "1.5rem", fontWeight: 600, color: "#caf0f8", letterSpacing: "-0.01em", lineHeight: 1, marginBottom: 4 }}>
          ${d.price?.toLocaleString()}
        </div>
        {/* Change */}
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <span style={{ fontSize: "0.7rem", color: changeColor }}>{isPos ? "+" : ""}{d.change}</span>
          <span style={{ fontSize: "0.7rem", color: changeColor, opacity: 0.7 }}>({isPos ? "+" : ""}{d.pct}%)</span>
        </div>
      </div>
      {/* Sparkline — flush to edges */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        <Sparkline closes={d.closes} isPositive={isPos} />
      </div>
      <div style={{ fontSize: "0.44rem", letterSpacing: "0.14em", color: "rgba(90,143,163,0.35)", textAlign: "right", padding: "3px 10px 6px" }}>
        1 MONTH
      </div>
    </div>
  );
}

// --- Image content ---

const PROXY = (url) => `http://localhost:8000/proxy-image?url=${encodeURIComponent(url)}`;

function ImageContent({ panel }) {
  const [loaded, setLoaded] = useState(false);
  const [src, setSrc] = useState(panel.url);
  const [err, setErr] = useState(false);

  const handleError = () => {
    if (src === panel.url) {
      setSrc(PROXY(panel.url));
    } else {
      setErr(true);
    }
  };

  return (
    <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden", position: "relative" }}>
      {!loaded && !err && (
        <span style={{ position: "absolute", fontSize: "0.5rem", letterSpacing: "0.2em", color: "rgba(245,158,11,0.4)", animation: "pulse 1.5s infinite" }}>
          LOADING...
        </span>
      )}
      {err ? (
        <span style={{ fontSize: "0.6rem", color: "rgba(90,143,163,0.45)", letterSpacing: "0.1em" }}>IMAGE UNAVAILABLE</span>
      ) : (
        <img
          src={src}
          alt={panel.title}
          onLoad={() => setLoaded(true)}
          onError={handleError}
          style={{
            maxWidth: "100%", maxHeight: "100%", objectFit: "contain",
            opacity: loaded ? 1 : 0,
            transition: "opacity 0.35s ease",
            display: "block",
          }}
        />
      )}
    </div>
  );
}

// --- Video / Webpage iframe content ---

function FrameContent({ url, title }) {
  return (
    <iframe
      src={url}
      title={title}
      sandbox="allow-scripts allow-same-origin allow-popups allow-forms"
      style={{ width: "100%", height: "100%", border: "none", display: "block" }}
      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      allowFullScreen
    />
  );
}

// --- Sports score ---

function TeamBlock({ team }) {
  const [imgErr, setImgErr] = useState(false);
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 5, width: 76 }}>
      {team?.logo && !imgErr ? (
        <img
          src={team.logo}
          alt={team.abbrev}
          onError={() => setImgErr(true)}
          style={{ width: 46, height: 46, objectFit: "contain", filter: "drop-shadow(0 0 8px rgba(0,180,216,0.15))" }}
        />
      ) : (
        <div style={{
          width: 46, height: 46, borderRadius: "50%",
          border: "1px solid rgba(0,180,216,0.2)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <span style={{ fontSize: "0.6rem", color: "#00b4d8" }}>{team?.abbrev}</span>
        </div>
      )}
      <span style={{ fontSize: "0.42rem", letterSpacing: "0.08em", color: "rgba(90,143,163,0.65)", textAlign: "center", lineHeight: 1.3 }}>
        {team?.name}
      </span>
      {team?.record && (
        <span style={{ fontSize: "0.38rem", color: "rgba(90,143,163,0.3)" }}>{team.record}</span>
      )}
    </div>
  );
}

function ScoreContent({ panel }) {
  const [data, setData] = useState(panel.data || {});

  useEffect(() => {
    if (!panel.game_id || data.status !== "live") return;
    const poll = async () => {
      try {
        const r = await fetch(
          `https://site.api.espn.com/apis/site/v2/sports/${panel.sport}/${panel.league}/summary?event=${panel.game_id}`
        );
        const json = await r.json();
        const comp = json.header?.competitions?.[0];
        if (!comp) return;
        const competitors = comp.competitors;
        const home = competitors.find(c => c.homeAway === "home") || competitors[0];
        const away = competitors.find(c => c.homeAway === "away") || competitors[1];
        const st = comp.status;
        const state = st.type.state;
        setData(prev => ({
          ...prev,
          home_team: { ...prev.home_team, score: home.score },
          away_team: { ...prev.away_team, score: away.score },
          status: state === "in" ? "live" : state === "post" ? "final" : "upcoming",
          status_display: state === "in" ? st.displayClock : st.type.description,
          period: st.period,
        }));
      } catch {}
    };
    const id = setInterval(poll, 30_000);
    return () => clearInterval(id);
  }, [panel.game_id, panel.sport, panel.league, data.status]);

  if (data.error) return (
    <div style={{ padding: "14px", fontSize: "0.58rem", color: "#ef233c", opacity: 0.75 }}>
      {data.error}
    </div>
  );

  const { home_team, away_team, status, status_display, period, series_summary } = data;
  const isLive = status === "live";

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", padding: "10px 14px" }}>
      {series_summary && (
        <div style={{ fontSize: "0.43rem", letterSpacing: "0.12em", color: "rgba(90,143,163,0.45)", textAlign: "center", marginBottom: 8 }}>
          {series_summary}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flex: 1 }}>
        <TeamBlock team={away_team} />
        <div style={{ textAlign: "center", flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
            <span style={{ fontSize: "2rem", fontWeight: 700, color: "#caf0f8", lineHeight: 1 }}>
              {away_team?.score ?? "–"}
            </span>
            <span style={{ fontSize: "1rem", color: "rgba(90,143,163,0.2)", lineHeight: 1 }}>–</span>
            <span style={{ fontSize: "2rem", fontWeight: 700, color: "#caf0f8", lineHeight: 1 }}>
              {home_team?.score ?? "–"}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 5, justifyContent: "center", marginTop: 7 }}>
            {isLive && (
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#ef233c", animation: "pulse 1s infinite" }} />
            )}
            <span style={{ fontSize: "0.5rem", letterSpacing: "0.1em", color: isLive ? "#ef233c" : "rgba(90,143,163,0.5)" }}>
              {isLive ? `Q${period} · ${status_display}` : (status === "final" ? "FINAL" : (status_display || "").toUpperCase())}
            </span>
          </div>
        </div>
        <TeamBlock team={home_team} />
      </div>
    </div>
  );
}

// --- Info card ---

function CardContent({ panel }) {
  const sections = panel.sections || [];
  const accent = "#f59e0b";
  return (
    <div className="scrollbar-hide" style={{ display: "flex", flexDirection: "column", height: "100%", overflowY: "auto" }}>
      {sections.map((section, i) => (
        <div key={i} style={{
          padding: "8px 14px",
          borderBottom: i < sections.length - 1 ? "1px solid rgba(245,158,11,0.08)" : "none",
        }}>
          {section.heading && (
            <div style={{
              fontSize: "0.62rem",
              letterSpacing: "0.2em",
              color: accent,
              opacity: 0.6,
              textTransform: "uppercase",
              marginBottom: 8,
            }}>
              {section.heading}
            </div>
          )}
          {(section.rows || []).map((row, j) => (
            <div key={j} style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              gap: 10,
              marginBottom: 6,
            }}>
              <span style={{ fontSize: "0.72rem", color: "rgba(90,143,163,0.65)", letterSpacing: "0.04em", flexShrink: 0 }}>
                {row.label}
              </span>
              <span style={{ fontSize: "0.82rem", color: "#caf0f8", opacity: 0.9, textAlign: "right", lineHeight: 1.4 }}>
                {row.value}
              </span>
            </div>
          ))}
        </div>
      ))}
      {panel.badge && (
        <div style={{
          padding: "6px 14px 8px",
          fontSize: "0.62rem",
          letterSpacing: "0.14em",
          color: accent,
          opacity: 0.45,
          textAlign: "center",
          textTransform: "uppercase",
          borderTop: "1px solid rgba(245,158,11,0.08)",
          marginTop: "auto",
        }}>
          {panel.badge}
        </div>
      )}
    </div>
  );
}

// --- Visual panel (wraps all visual content types except map) ---

// Research panel anchor: right edge, top 10% — image panels sit just to its left
const RESEARCH_X = () => window.innerWidth - 286;
const RESEARCH_Y = () => Math.floor(window.innerHeight * 0.10);

function VisualPanel({ panel, onDismiss }) {
  const cfg = VISUAL_CONFIG[panel.content_type] || VISUAL_CONFIG.webpage;

  // Images appear to the left of the research panel, aligned to its top
  const defaultX = panel.content_type === "image"
    ? RESEARCH_X() - cfg.defaultW - 10
    : Math.floor(window.innerWidth * 0.55 - cfg.defaultW / 2);
  const defaultY = panel.content_type === "image"
    ? RESEARCH_Y()
    : Math.floor(window.innerHeight * 0.18);

  return (
    <DraggableWindow
      label={cfg.label}
      accentColor={cfg.color}
      defaultX={defaultX}
      defaultY={defaultY}
      defaultW={cfg.defaultW}
      defaultH={cfg.defaultH}
      minW={200}
      minH={120}
      baseZ={25}
      onClose={() => onDismiss(panel.id)}
    >
      {panel.content_type === "stock"   && <StockContent panel={panel} />}
      {panel.content_type === "image"   && <ImageContent panel={panel} />}
      {panel.content_type === "score"   && <ScoreContent panel={panel} />}
      {panel.content_type === "card"    && <CardContent panel={panel} />}
      {(panel.content_type === "video" || panel.content_type === "webpage") && (
        <FrameContent url={panel.url} title={panel.title} />
      )}
    </DraggableWindow>
  );
}

// --- Agent result panel ---

function AgentPanel({ panel, cfg, onDismiss }) {
  return (
    <DraggableWindow
      label={cfg.label}
      accentColor={cfg.color}
      defaultX={window.innerWidth - 286}
      defaultY={cfg.defaultY()}
      defaultW={274}
      defaultH={260}
      minW={180}
      minH={100}
      baseZ={20}
      onClose={() => onDismiss(panel.id)}
    >
      <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
        {panel.title && (
          <div style={{
            padding: "5px 12px 4px",
            fontSize: "0.55rem",
            letterSpacing: "0.06em",
            color: cfg.color,
            opacity: 0.45,
            borderBottom: `1px solid ${cfg.color}10`,
            flexShrink: 0,
            lineHeight: 1.4,
          }}>
            {panel.title}
          </div>
        )}
        <div
          className="scrollbar-hide"
          style={{
            flex: 1,
            overflowY: "auto",
            padding: "8px 12px",
            fontSize: "0.63rem",
            lineHeight: 1.7,
            color: "#caf0f8",
            opacity: 0.82,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {panel.content}
        </div>
      </div>
    </DraggableWindow>
  );
}

const AGENT_POSITIONS = {
  research: () => Math.floor(window.innerHeight * 0.10),
  code:     () => Math.floor(window.innerHeight * 0.40),
  task:     () => Math.floor(window.innerHeight * 0.65),
};

// --- Root export ---

export default function HudPanels({ panels, onDismiss }) {
  if (!panels.length) return null;
  return (
    <div className="absolute inset-0 pointer-events-none z-20">
      {panels.map(panel => {
        if (panel.panel_type === "visual") {
          if (panel.content_type === "map") {
            return (
              <div key={panel.id} className="pointer-events-auto">
                <GlobeViewer panel={panel} onDismiss={onDismiss} />
              </div>
            );
          }
          return (
            <div key={panel.id} className="pointer-events-auto">
              <VisualPanel panel={panel} onDismiss={onDismiss} />
            </div>
          );
        }
        const agentCfg = AGENT_CONFIG[panel.panel_type];
        if (!agentCfg) return null;
        const cfg = {
          ...agentCfg,
          defaultY: AGENT_POSITIONS[panel.panel_type] || (() => Math.floor(window.innerHeight * 0.3)),
        };
        return (
          <div key={panel.id} className="pointer-events-auto">
            <AgentPanel panel={panel} cfg={cfg} onDismiss={onDismiss} />
          </div>
        );
      })}
    </div>
  );
}
