import React, { useEffect, useRef, useState } from "react";

export default function ConversationFeed({ messages, onSendText, onVoiceStart, onStopSpeaking, status }) {
  const bottomRef = useRef(null);
  const [input, setInput] = useState("");

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSubmit(e) {
    e.preventDefault();
    const text = input.trim();
    if (!text) return;
    if (text.toLowerCase() === "stop") {
      onStopSpeaking();
      setInput("");
      return;
    }
    onSendText(text);
    setInput("");
  }

  const isListening = status === "listening";
  const isActive = status !== "idle";

  return (
    <div className="flex flex-col h-full">
      {/* Messages — fade at top */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5 scrollbar-hide"
        style={{ maskImage: "linear-gradient(to bottom, transparent 0%, black 18%)" }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <span className="text-xs tracking-widest opacity-30 text-hud-muted">
              {msg.role === "user" ? "YOU" : "HORUS"}
            </span>
            <div
              className={`max-w-xs px-3 py-2 rounded text-sm leading-relaxed ${
                msg.role === "user"
                  ? "text-hud-text opacity-70"
                  : "text-hud-glow opacity-90"
              }`}
            >
              {msg.content}
              {msg.streaming && (
                <span className="inline-block w-1.5 h-3.5 ml-0.5 bg-hud-glow opacity-80 animate-pulse align-middle" />
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Input bar — minimal, no border box */}
      <div className="px-4 py-4">
        <form onSubmit={handleSubmit} className="flex gap-2 items-center">
          {isActive ? (
            <button
              type="button"
              onClick={onStopSpeaking}
              className="text-xs tracking-widest transition-all px-2 py-1 rounded text-red-400 animate-pulse hover:text-red-300"
            >
              ■ STOP
            </button>
          ) : (
            <button
              type="button"
              onClick={onVoiceStart}
              className="text-xs tracking-widest transition-all px-2 py-1 rounded text-hud-muted opacity-50 hover:opacity-100 hover:text-hud-accent"
            >
              {isListening ? "● REC" : "MIC"}
            </button>
          )}
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="say something..."
            className="flex-1 bg-transparent border-b border-hud-border focus:border-hud-accent outline-none text-sm text-hud-text placeholder-hud-muted py-1 transition-colors"
          />
          <button
            type="submit"
            className="text-xs tracking-widest text-hud-muted hover:text-hud-accent opacity-50 hover:opacity-100 transition-all px-2"
          >
            →
          </button>
        </form>
      </div>
    </div>
  );
}
