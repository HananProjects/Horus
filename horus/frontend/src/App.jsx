import React, { useEffect, useRef, useState } from "react";
import Dashboard from "./components/Dashboard";

const WS_URL = "ws://localhost:8000/ws";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState("idle");
  const [actions, setActions] = useState([]);
  const [memories, setMemories] = useState([]);
  const [nodes, setNodes] = useState([]);
  const [panels, setPanels] = useState([]);
  const [pendingConfirm, setPendingConfirm] = useState(null);
  const [settings, setSettings] = useState({
    computer_use_enabled: true,
    wake_word_enabled: false,
    voice_rate: 185,
  });
  const ws = useRef(null);

  useEffect(() => {
    connect();
    return () => ws.current?.close();
  }, []);

  function connect() {
    ws.current = new WebSocket(WS_URL);

    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.type === "status") {
        setStatus(data.status);
      } else if (data.type === "message") {
        setMessages((prev) => [...prev, { role: data.role, content: data.content, ts: Date.now() }]);
      } else if (data.type === "action") {
        if (data.action) {
          setActions((prev) => [{ text: data.action, ts: Date.now() }, ...prev].slice(0, 50));
        }
      } else if (data.type === "memories") {
        setMemories(data.memories);
      } else if (data.type === "nodes") {
        setNodes(data.nodes);
      } else if (data.type === "panel") {
        setPanels(prev => {
          const filtered = prev.filter(p => p.panel_type !== data.panel_type);
          return [...filtered, { ...data, id: Date.now() }];
        });
      } else if (data.type === "confirm_action") {
        setPendingConfirm(data.description);
      } else if (data.type === "settings") {
        setSettings(data.settings);
      } else if (data.type === "wake_word") {
        startVoice();
      }
    };

    ws.current.onclose = () => setTimeout(connect, 2000);
  }

  function sendText(text) {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "text", content: text }));
      setMessages((prev) => [...prev, { role: "user", content: text, ts: Date.now() }]);
    }
  }

  function startVoice() {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "voice_start" }));
    }
  }

  function handleConfirm(approved) {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "confirm_response", approved }));
    }
    setPendingConfirm(null);
  }

  function updateSettings(newSettings) {
    setSettings(newSettings);
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "update_settings", settings: newSettings }));
    }
  }

  function clearMemory() {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "clear_memory" }));
    }
  }

  function dismissPanel(id) {
    setPanels(prev => prev.filter(p => p.id !== id));
  }

  function removeNode(nodeId) {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "remove_node", node_id: nodeId }));
    }
  }

  function nodeAction(nodeId, action) {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "node_action", node_id: nodeId, action }));
    }
  }

  return (
    <Dashboard
      messages={messages}
      status={status}
      actions={actions}
      memories={memories}
      nodes={nodes}
      panels={panels}
      pendingConfirm={pendingConfirm}
      settings={settings}
      onSendText={sendText}
      onVoiceStart={startVoice}
      onConfirmApprove={() => handleConfirm(true)}
      onConfirmDeny={() => handleConfirm(false)}
      onUpdateSettings={updateSettings}
      onClearMemory={clearMemory}
      onRemoveNode={removeNode}
      onNodeAction={nodeAction}
      onDismissPanel={dismissPanel}
    />
  );
}
