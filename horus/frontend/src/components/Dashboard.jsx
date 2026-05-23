import React, { useState } from "react";
import ConfirmModal from "./ConfirmModal";
import SettingsPanel from "./SettingsPanel";
import NeuralSphere from "./NeuralSphere";
import ConversationFeed from "./ConversationFeed";
import NodeOrbit from "./NodeOrbit";
import HudPanels from "./HudPanel";
import DraggableWindow from "./DraggableWindow";
import LearningLog from "./LearningLog";

const CORNER_STYLE = (pos) => ({
  position: "absolute",
  width: 18,
  height: 18,
  ...pos,
  borderTop: pos.top !== undefined ? "1px solid rgba(0,180,216,0.22)" : undefined,
  borderBottom: pos.bottom !== undefined ? "1px solid rgba(0,180,216,0.22)" : undefined,
  borderLeft: pos.left !== undefined ? "1px solid rgba(0,180,216,0.22)" : undefined,
  borderRight: pos.right !== undefined ? "1px solid rgba(0,180,216,0.22)" : undefined,
  pointerEvents: "none",
});

export default function Dashboard({
  messages, status, actions, memories, nodes, edges, panels, pendingConfirm, settings, micDevices,
  learningUpdates, onClearLearning,
  onSendText, onVoiceStart, onStopSpeaking, onConfirmApprove, onConfirmDeny,
  onUpdateSettings, onClearMemory, onRemoveNode, onNodeAction, onDismissPanel,
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const currentAction = actions[0]?.text ?? "";

  return (
    <div className="fixed inset-0 bg-hud-bg font-mono overflow-hidden">
      {/* Scan lines overlay */}
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none", zIndex: 60,
        backgroundImage: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.07) 2px, rgba(0,0,0,0.07) 4px)",
      }} />

      {/* Corner brackets */}
      <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 30 }}>
        <div style={CORNER_STYLE({ top: 14, left: 14, borderTop: "1px solid rgba(0,180,216,0.22)", borderLeft: "1px solid rgba(0,180,216,0.22)" })} />
        <div style={CORNER_STYLE({ top: 14, right: 14, borderTop: "1px solid rgba(0,180,216,0.22)", borderRight: "1px solid rgba(0,180,216,0.22)" })} />
        <div style={CORNER_STYLE({ bottom: 14, left: 14, borderBottom: "1px solid rgba(0,180,216,0.22)", borderLeft: "1px solid rgba(0,180,216,0.22)" })} />
        <div style={CORNER_STYLE({ bottom: 14, right: 14, borderBottom: "1px solid rgba(0,180,216,0.22)", borderRight: "1px solid rgba(0,180,216,0.22)" })} />
      </div>

      <ConfirmModal
        description={pendingConfirm}
        onApprove={onConfirmApprove}
        onDeny={onConfirmDeny}
      />

      <SettingsPanel
        open={settingsOpen}
        settings={settings}
        micDevices={micDevices}
        onUpdateSettings={onUpdateSettings}
        onClearMemory={() => { onClearMemory(); setSettingsOpen(false); }}
        onClose={() => setSettingsOpen(false)}
      />

      {/* Sphere fills everything */}
      <div className="absolute inset-0">
        <NeuralSphere status={status} nodeCount={nodes.length} />
      </div>

      {/* Orbital project nodes */}
      <NodeOrbit nodes={nodes} edges={edges ?? []} onRemove={onRemoveNode} onNodeAction={onNodeAction} />

      {/* Right-side floating data panels */}
      <HudPanels panels={panels ?? []} onDismiss={onDismissPanel} />

      {/* Learning discoveries overlay */}
      {learningUpdates?.length > 0 && (
        <div className="absolute top-0 left-0 right-0 z-50">
          <LearningLog updates={learningUpdates} onClear={onClearLearning} />
        </div>
      )}

      {/* Top-left: wordmark */}
      <div className="absolute top-4 left-5 z-40 pointer-events-none">
        <span className="text-hud-glow font-bold tracking-widest text-sm opacity-50">HORUS</span>
      </div>

      {/* Top-right: status + settings */}
      <div className="absolute top-4 right-5 flex items-center gap-4 z-10">
        {status !== "idle" && (
          <span className="text-xs tracking-widest text-hud-accent uppercase opacity-80 animate-pulse">
            {status}
          </span>
        )}
        <button
          onClick={() => setSettingsOpen(true)}
          className="text-hud-muted hover:text-hud-accent text-xs tracking-widest opacity-40 hover:opacity-100 transition-all"
        >
          ⚙
        </button>
      </div>

      {/* Conversation feed — draggable window */}
      <div className="absolute inset-0 pointer-events-none z-10">
        <div className="pointer-events-auto">
          <DraggableWindow
            label="COMM"
            accentColor="#00b4d8"
            defaultX={12}
            defaultY={60}
            defaultW={272}
            defaultH={Math.floor(window.innerHeight - 90)}
            minW={200}
            minH={200}
            baseZ={10}
          >
            <ConversationFeed
              messages={messages}
              onSendText={onSendText}
              onVoiceStart={onVoiceStart}
              onStopSpeaking={onStopSpeaking}
              status={status}
            />
          </DraggableWindow>
        </div>
      </div>

      {/* Bottom-center: current action ticker */}
      <div className="absolute bottom-6 left-0 right-0 flex justify-center z-10 pointer-events-none">
        {status !== "idle" && currentAction ? (
          <span style={{
            fontSize: "0.52rem",
            letterSpacing: "0.18em",
            color: "rgba(0,229,255,0.45)",
            textTransform: "uppercase",
          }}>
            ▶ {currentAction}
          </span>
        ) : status === "idle" ? (
          <span className="text-xs tracking-widest text-hud-muted opacity-20 uppercase">standby</span>
        ) : null}
      </div>

      {/* Bottom-right: telemetry */}
      <div style={{
        position: "absolute", bottom: 20, right: 22,
        fontSize: "0.46rem", letterSpacing: "0.15em",
        color: "rgba(0,180,216,0.2)", textAlign: "right",
        pointerEvents: "none", zIndex: 10, lineHeight: 1.8,
      }}>
        <div>SYS · {status.toUpperCase()}</div>
        <div>NODES · {nodes.length}</div>
      </div>
    </div>
  );
}
