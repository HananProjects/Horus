import React, { useEffect, useRef, useState } from "react";

export default function ConversationFeed({ messages, onSendText, onVoiceStart, status }) {
  const bottomRef = useRef(null);
  const [input, setInput] = useState("");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSubmit(e) {
    e.preventDefault();
    if (!input.trim()) return;
    onSendText(input.trim());
    setInput("");
  }

  const isListening = status === "listening";

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-2 border-b border-hud-border text-xs text-hud-muted tracking-widest">
        CONVERSATION
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-hud-muted text-sm text-center mt-12 opacity-50">
            Awaiting input...
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <span className="text-xs text-hud-muted tracking-wider">
              {msg.role === "user" ? "HANAN" : "HORUS"}
            </span>
            <div
              className={`max-w-lg px-4 py-3 rounded text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-hud-accent2/20 border border-hud-accent2 text-hud-text"
                  : "bg-hud-panel border border-hud-border text-hud-glow shadow-glow"
              }`}
            >
              {msg.content}
              {msg.role === "assistant" && <span className="animate-blink ml-1">_</span>}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input bar */}
      <div className="border-t border-hud-border px-4 py-3">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <button
            type="button"
            onClick={onVoiceStart}
            disabled={status !== "idle"}
            className={`px-3 py-2 rounded border text-xs tracking-wider transition-all ${
              isListening
                ? "border-hud-success text-hud-success animate-pulse-glow"
                : "border-hud-border text-hud-muted hover:border-hud-accent hover:text-hud-accent"
            }`}
          >
            {isListening ? "● REC" : "MIC"}
          </button>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            className="flex-1 bg-hud-panel border border-hud-border rounded px-3 py-2 text-sm text-hud-text placeholder-hud-muted focus:outline-none focus:border-hud-accent"
          />
          <button
            type="submit"
            className="px-4 py-2 bg-hud-accent2/20 border border-hud-accent text-hud-accent text-xs tracking-wider rounded hover:bg-hud-accent/20 transition-all"
          >
            SEND
          </button>
        </form>
      </div>
    </div>
  );
}
