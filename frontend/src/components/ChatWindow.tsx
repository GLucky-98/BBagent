import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, HelpCircle, X, ChevronDown, Plus } from "lucide-react";
import { useAppStore, useSelectedAgent, useAgentModel } from "../store";
import { cn } from "../lib/utils";
import type { Message, SessionInfo } from "../types";

const EMPTY_SESSIONS: SessionInfo[] = [];

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";
  const isThinking = message.chunkType === "thinking";
  const isTool = message.chunkType === "tool_use" || message.chunkType === "tool_result";

  if (isSystem) {
    return (
      <div className="flex justify-center mb-4">
        <span className="text-xs text-[--color-muted-foreground] bg-[--color-muted] px-3 py-1 rounded-full">
          {message.content}
        </span>
      </div>
    );
  }

  if (isThinking) {
    return (
      <div className="flex gap-3 mb-4">
        <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-purple-100">
          <Bot size={16} className="text-purple-600" />
        </div>
        <div className="max-w-[70%] rounded-2xl px-4 py-2.5 bg-purple-50 rounded-tl-sm">
          <p className="text-xs text-purple-600 font-medium mb-1">Thinking</p>
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-purple-700/70 italic">{message.content}</p>
        </div>
      </div>
    );
  }

  if (isTool) {
    const label = message.chunkType === "tool_use" ? `Calling: ${message.toolName}` : `Result: ${message.toolName}`;
    return (
      <div className="flex gap-3 mb-4">
        <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-orange-100">
          <Bot size={16} className="text-orange-600" />
        </div>
        <div className="max-w-[70%] rounded-2xl px-4 py-2.5 bg-orange-50 rounded-tl-sm">
          <p className="text-xs text-orange-600 font-medium mb-1">{label}</p>
          <pre className="text-xs whitespace-pre-wrap text-orange-700/70 max-h-32 overflow-y-auto">{message.content}</pre>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex gap-3 mb-4", isUser ? "flex-row-reverse" : "flex-row")}>
      <div className={cn("w-8 h-8 rounded-full flex items-center justify-center shrink-0", isUser ? "bg-[--color-primary] text-[--color-primary-foreground]" : "bg-[--color-secondary]")}>
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      <div className={cn("max-w-[70%] rounded-2xl px-4 py-2.5", isUser ? "bg-[--color-primary] text-[--color-primary-foreground] rounded-tr-sm" : "bg-[--color-secondary] rounded-tl-sm")}>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        <span className={cn("text-[10px] mt-1 block", isUser ? "text-[--color-primary-foreground]/60" : "text-[--color-muted-foreground]")}>
          {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}

export function ChatWindow() {
  const selectedAgent = useSelectedAgent();
  const agentModel = useAgentModel();
  const addMessage = useAppStore((s) => s.addMessage);
  const agentState = useAppStore((s) => s.agentStates[selectedAgent?.name || ""] || selectedAgent?.state || "ready");
  const isStreaming = useAppStore((s) => s.isAgentStreaming[selectedAgent?.name || ""] || false);
  const setIsStreaming = useAppStore((s) => s.setIsStreaming);
  const setAgentState = useAppStore((s) => s.setAgentState);
  const updateAgent = useAppStore((s) => s.updateAgent);
  const loadAgentSessions = useAppStore((s) => s.loadAgentSessions);
  const agentSessions = useAppStore((s) => s.agentSessions[selectedAgent?.name || ""]) || EMPTY_SESSIONS;
  const switchSession = useAppStore((s) => s.switchSession);
  const createNewSession = useAppStore((s) => s.createNewSession);
  const loadAgentMessages = useAppStore((s) => s.loadAgentMessages);

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const agentNameRef = useRef<string | null>(null);
  const streamBufferRef = useRef("");

  const [humanQuestion, setHumanQuestion] = useState<string | null>(null);
  const [humanAnswer, setHumanAnswer] = useState("");
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const sessionDropdownRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => { scrollToBottom(); }, [selectedAgent?.messages, humanQuestion]);

  const connectWs = useCallback((agentName: string) => {
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close();
    }
    const wsBase = (import.meta.env.VITE_API_BASE || "http://localhost:8000/api").replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/ws/chat/${agentName}`);
    wsRef.current = ws;
    agentNameRef.current = agentName;
    streamBufferRef.current = "";

    ws.onmessage = (event) => {
      try {
        const chunk = JSON.parse(event.data);
        const name = agentNameRef.current;
        if (!name) return;

        if (chunk.type === "text" && chunk.content) {
          streamBufferRef.current += chunk.content;
          useAppStore.getState().setIsStreaming(name, true);
          useAppStore.getState().setAgentState(name, "running");
          const state = useAppStore.getState();
          const currentMsgs = state.agents.find((a) => a.name === name)?.messages || [];
          const lastMsg = currentMsgs[currentMsgs.length - 1];
          if (lastMsg && lastMsg.role === "assistant" && lastMsg.chunkType !== "tool_use") {
            const updatedMsgs = [...currentMsgs];
            updatedMsgs[updatedMsgs.length - 1] = { ...updatedMsgs[updatedMsgs.length - 1], content: streamBufferRef.current };
            state.updateAgent(name, { messages: updatedMsgs });
          } else {
            state.addMessage(name, {
              id: crypto.randomUUID(),
              role: "assistant",
              content: chunk.content,
              timestamp: Date.now(),
              messageId: chunk.message_id,
            });
          }
        } else if (chunk.type === "thinking" && chunk.content) {
          addMessage(name, {
            id: crypto.randomUUID(),
            role: "system",
            content: chunk.content,
            timestamp: Date.now(),
            chunkType: "thinking",
          });
        } else if (chunk.type === "completed_tool_use") {
          addMessage(name, {
            id: crypto.randomUUID(),
            role: "system",
            content: JSON.stringify(chunk.content?.input || {}, null, 2),
            timestamp: Date.now(),
            chunkType: "tool_use",
            toolName: chunk.content?.name || "",
            toolInput: chunk.content?.input || {},
          });
        } else if (chunk.type === "tool_results") {
          const results = chunk.content;
          if (Array.isArray(results)) {
            for (const r of results) {
              addMessage(name, {
                id: crypto.randomUUID(),
                role: "system",
                content: typeof r === "string" ? r : JSON.stringify(r),
                timestamp: Date.now(),
                chunkType: "tool_result",
                toolName: r.name || "",
              });
            }
          }
        } else if (chunk.type === "human_question") {
          setHumanQuestion(chunk.content);
        } else if (chunk.type === "completed_message") {
          streamBufferRef.current = "";
          setIsStreaming(name, false);
        } else if (chunk.type === "interrupted") {
          streamBufferRef.current = "";
          setIsStreaming(name, false);
        } else if (chunk.type === "agent_state") {
          setAgentState(name, chunk.state);
          if (chunk.state !== "running") {
            setIsStreaming(name, false);
          }
        } else if (chunk.type === "error") {
          addMessage(name, {
            id: crypto.randomUUID(),
            role: "system",
            content: `Error: ${chunk.content}`,
            timestamp: Date.now(),
            chunkType: "error",
          });
          setIsStreaming(name, false);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setIsStreaming(agentName, false);
    };

    ws.onerror = () => {
      // Connection error handled by onclose
    };
  }, [addMessage]);

  useEffect(() => {
    if (selectedAgent) {
      loadAgentMessages(selectedAgent.name);
      loadAgentSessions(selectedAgent.name);
      connectWs(selectedAgent.name);
    }
    return () => {
      wsRef.current?.close();
    };
  }, [selectedAgent?.name, connectWs, loadAgentMessages, loadAgentSessions]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (sessionDropdownRef.current && !sessionDropdownRef.current.contains(e.target as Node)) {
        setSessionDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSend = () => {
    if (!input.trim() || !selectedAgent) return;
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: input.trim(), timestamp: Date.now() };
    addMessage(selectedAgent.name, userMessage);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "user_message", content: input.trim() }));
    }
    setInput("");
  };

  const handleInterrupt = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "interrupt" }));
    }
  };

  const handleHumanSubmit = () => {
    if (!humanAnswer.trim() || !selectedAgent) return;
    const answerMessage: Message = { id: crypto.randomUUID(), role: "user", content: humanAnswer.trim(), timestamp: Date.now() };
    addMessage(selectedAgent.name, answerMessage);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "human_answer", content: humanAnswer.trim() }));
    }
    setHumanQuestion(null);
    setHumanAnswer("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (humanQuestion) {
        handleHumanSubmit();
      } else if (isStreaming) {
        handleInterrupt();
      } else {
        handleSend();
      }
    }
  };

  const activeSession = agentSessions.find((s) => s.isActive);
  const currentSessionId = selectedAgent?.currentSessionId || activeSession?.id || "";

  if (!selectedAgent) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
        <Bot size={48} className="mb-4 opacity-30" />
        <p className="text-lg font-medium">No agent selected</p>
        <p className="text-sm mt-1">Select an agent to start chatting</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-[--color-background]">
      <header className="px-6 py-4 bg-white border-b border-[--color-border]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-[--color-primary]/10 flex items-center justify-center">
            <Bot size={20} className="text-[--color-primary]" />
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-[--color-foreground]">{selectedAgent.name}</h2>
            <p className="text-xs text-[--color-muted-foreground]">
              {selectedAgent.type === "team" ? "Agent Team" : "Single Agent"}{agentModel ? ` \u2022 ${agentModel.name}` : ""}
              <span className={cn(
                "ml-2 inline-block w-1.5 h-1.5 rounded-full",
                isStreaming && "bg-green-500 animate-pulse",
                agentState === "waiting" && "bg-green-500",
                agentState === "running" && "bg-blue-500 animate-pulse",
                agentState === "error" && "bg-red-500",
                agentState === "ready" && "bg-gray-400"
              )} />
              <span className="ml-1 capitalize">{agentState}</span>
            </p>
          </div>
          <div className="relative" ref={sessionDropdownRef}>
            <button
              onClick={() => { setSessionDropdownOpen(!sessionDropdownOpen); }}
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-[--color-border] hover:bg-[--color-secondary] transition-colors"
            >
              <span className="max-w-[120px] truncate">
                {currentSessionId ? currentSessionId.substring(0, 19) : "No session"}
              </span>
              <ChevronDown size={12} />
            </button>
            {sessionDropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-64 bg-white rounded-lg shadow-lg border border-[--color-border] z-50 max-h-60 overflow-y-auto">
                {agentSessions.map((s: SessionInfo) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      switchSession(selectedAgent.name, s.id);
                      setSessionDropdownOpen(false);
                    }}
                    className={cn(
                      "w-full text-left px-3 py-2 text-xs hover:bg-[--color-secondary] transition-colors",
                      s.isActive && "bg-[--color-primary]/10 text-[--color-primary]"
                    )}
                  >
                    <div className="font-medium truncate">{s.id.substring(0, 19)}</div>
                    <div className="text-[--color-muted-foreground]">
                      {s.turnCount} turns {s.isActive && "(active)"}
                    </div>
                  </button>
                ))}
                {agentSessions.length === 0 && (
                  <div className="px-3 py-2 text-xs text-[--color-muted-foreground]">No sessions found</div>
                )}
                <div className="border-t border-[--color-border]">
                  <button
                    onClick={() => {
                      createNewSession(selectedAgent.name);
                      setSessionDropdownOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-[--color-primary] hover:bg-[--color-secondary] flex items-center gap-1"
                  >
                    <Plus size={12} />
                    New Session
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {(!selectedAgent.messages || selectedAgent.messages.length === 0) ? (
          <div className="h-full flex flex-col items-center justify-center text-[--color-muted-foreground]">
            <div className="w-16 h-16 rounded-full bg-[--color-secondary] flex items-center justify-center mb-4"><Bot size={28} /></div>
            <p className="text-sm">Start a conversation</p>
            <p className="text-xs mt-1">Send a message to begin</p>
          </div>
        ) : (
          selectedAgent.messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)
        )}
        <div ref={messagesEndRef} />
      </div>
      {humanQuestion ? (
        <div className="p-4 bg-amber-50 border-t border-amber-200">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center shrink-0 mt-0.5">
              <HelpCircle size={16} className="text-amber-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800 mb-2">{humanQuestion}</p>
              <div className="flex items-end gap-2">
                <input
                  type="text"
                  value={humanAnswer}
                  onChange={(e) => setHumanAnswer(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Your answer..."
                  autoFocus
                  className="flex-1 px-3 py-2 rounded-lg border border-amber-300 bg-white focus:outline-none focus:ring-2 focus:ring-amber-400 text-sm"
                />
                <button
                  onClick={handleHumanSubmit}
                  disabled={!humanAnswer.trim()}
                  className="px-4 py-2 rounded-lg bg-amber-500 text-white hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors"
                >
                  Answer
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-4 bg-white border-t border-[--color-border]">
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Type a message..." rows={1}
                className={cn("w-full px-4 py-3 rounded-xl border border-[--color-border]", "bg-[--color-background] resize-none", "focus:outline-none focus:ring-2 focus:ring-[--color-ring] focus:border-transparent", "placeholder:text-[--color-muted-foreground]")}
                style={{ minHeight: "48px", maxHeight: "120px" }} />
            </div>
            {isStreaming ? (
              <button onClick={handleInterrupt}
                className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border border-[--color-border] bg-red-500 text-white transition-all duration-200 hover:opacity-90">
                <X size={18} />
              </button>
            ) : (
              <button onClick={handleSend} disabled={!input.trim()}
                className={cn("w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border border-[--color-border]", "bg-[--color-primary] text-[--color-primary-foreground]", "transition-all duration-200", "hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed")}>
                <Send size={18} />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
