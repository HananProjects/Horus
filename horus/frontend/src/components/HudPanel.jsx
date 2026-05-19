import DraggableWindow from "./DraggableWindow";

const TYPE_CONFIG = {
  research: {
    label: "RESEARCH",
    color: "#00e5ff",
    defaultY: () => Math.floor(window.innerHeight * 0.10),
  },
  code: {
    label: "CODE",
    color: "#06d6a0",
    defaultY: () => Math.floor(window.innerHeight * 0.40),
  },
  task: {
    label: "TASK",
    color: "#f59e0b",
    defaultY: () => Math.floor(window.innerHeight * 0.65),
  },
};

function Panel({ panel, cfg, onDismiss }) {
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

export default function HudPanels({ panels, onDismiss }) {
  if (!panels.length) return null;
  return (
    <div className="absolute inset-0 pointer-events-none z-20">
      {panels.map(panel => {
        const cfg = TYPE_CONFIG[panel.panel_type] || TYPE_CONFIG.research;
        return (
          <div key={panel.id} className="pointer-events-auto">
            <Panel panel={panel} cfg={cfg} onDismiss={onDismiss} />
          </div>
        );
      })}
    </div>
  );
}
