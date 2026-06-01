import { useState, useRef, useEffect } from "react";
import { flushSync } from "react-dom";
import { Send, Bot, User, HelpCircle, Square, ChevronDown, ChevronRight, Plus } from "lucide-react";
import { useAppStore, useSelectedAgent, useAgentModel } from "../store";
import { cn } from "../lib/utils";
import { createChatWs } from "../lib/api";
import type { Message, SessionInfo } from "../types";

const EMPTY_SESSIONS: SessionInfo[] = [];

// ── Standalone message bubble (user message or system notification) ──
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isSystemNotification = message.role === "system" && !message.chunkType;

  if (isUser) {
    return (
      <div className="flex gap-3 mb-4 flex-row-reverse">
        <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-(--color-primary) text-(--color-primary-foreground)">
          <User size={16} />
        </div>
        <div className="max-w-[70%] rounded-2xl px-4 py-2.5 bg-(--color-primary) text-(--color-primary-foreground) rounded-tr-sm">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
          <span className="text-[10px] mt-1 block text-(--color-primary-foreground)/60">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
      </div>
    );
  }

  if (isSystemNotification) {
    return (
      <div className="flex justify-center mb-4">
        <span className="text-xs text-(--color-muted-foreground) bg-(--color-muted) px-3 py-1 rounded-full">
          {message.content}
        </span>
      </div>
    );
  }

  // Default: assistant text (standalone, outside a group)
  return (
    <div className="flex gap-3 mb-4">
      <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-(--color-secondary)">
        <Bot size={16} />
      </div>
      <div className="max-w-[70%] rounded-2xl px-4 py-2.5 bg-(--color-secondary) rounded-tl-sm">
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        <span className="text-[10px] mt-1 block text-(--color-muted-foreground)">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}

// ── Grouping helpers ──

function sectionLabel(msg: Message): string {
  switch (msg.chunkType) {
    case "thinking": return "Thinking";
    case "tool_use": return `Calling: ${msg.toolName || ""}`;
    case "tool_result": return `Result: ${msg.toolName || ""}`;
    case "error": return "Error";
    default: return "";
  }
}

function sectionColor(msg: Message): string {
  switch (msg.chunkType) {
    case "thinking": return "purple";
    case "tool_use":
    case "tool_result": return "orange";
    case "error": return "red";
    default: return "gray";
  }
}

function shouldDefaultExpand(msg: Message, isStreaming: boolean): boolean {
  if (isStreaming) return true;
  // Text and standalone assistant messages are always visible.
  if (!msg.chunkType || msg.chunkType === "text") return true;
  return false;
}

function isStandalone(msg: Message): boolean {
  return msg.role === "user" || (msg.role === "system" && !msg.chunkType);
}

function buildSegments(messages: Message[]): Message[][] {
  const segments: Message[][] = [];
  for (const msg of messages) {
    if (isStandalone(msg)) {
      segments.push([msg]);
    } else {
      const last = segments[segments.length - 1];
      if (last && last.length > 0 && !isStandalone(last[0])) {
        last.push(msg);
      } else {
        segments.push([msg]);
      }
    }
  }
  return segments;
}

const SECTION_COLORS: Record<string, { bg: string; icon: string; text: string; light: string; label: string }> = {
  purple:  { bg: "bg-purple-100", icon: "text-purple-600", text: "text-purple-700/70", light: "bg-purple-50", label: "text-purple-600" },
  orange:  { bg: "bg-orange-100", icon: "text-orange-600", text: "text-orange-700/70", light: "bg-orange-50", label: "text-orange-600" },
  red:     { bg: "bg-red-100",    icon: "text-red-600",    text: "text-red-700/70",    light: "bg-red-50",    label: "text-red-600" },
  gray:    { bg: "bg-(--color-secondary)", icon: "text-(--color-muted-foreground)", text: "text-(--color-foreground)", light: "bg-(--color-secondary)", label: "text-(--color-muted-foreground)" },
};

// ── A single collapsible section within a message group ──
function GroupSection({
  msg, isExpanded, onToggle, showDivider,
}: {
  msg: Message; isExpanded: boolean; onToggle: () => void; showDivider: boolean;
}) {
  const color = SECTION_COLORS[sectionColor(msg)] ?? SECTION_COLORS.gray;
  const label = sectionLabel(msg);
  const isText = !msg.chunkType || msg.chunkType === "text";

  if (isText) {
    return (
      <div className={cn("px-4 py-3", showDivider && "border-t border-(--color-border)/50")}>
        <p className="text-sm leading-relaxed whitespace-pre-wrap text-(--color-foreground)">{msg.content}</p>
      </div>
    );
  }

  return (
    <div className={cn(color.light, showDivider && "border-t border-(--color-border)/50")}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-4 py-2 text-left hover:opacity-80 transition-opacity"
      >
        <span className="shrink-0">
          {isExpanded ? <ChevronDown size={14} className={color.icon} /> : <ChevronRight size={14} className={color.icon} />}
        </span>
        <span className={cn("text-xs font-medium", color.label)}>{label}</span>
      </button>
      {isExpanded && (
        <div className="px-4 pb-3">
          <pre className={cn("text-xs whitespace-pre-wrap max-h-32 overflow-y-auto", color.text)}>
            {msg.content}
          </pre>
        </div>
      )}
    </div>
  );
}

// ── Composite bubble for a group of adjacent non-user messages ──
function MessageGroup({
  messages, isStreaming, collapsedSections, onToggleSection,
}: {
  messages: Message[]; isStreaming: boolean;
  collapsedSections: Set<string>; onToggleSection: (id: string) => void;
}) {
  const timestamp = messages[messages.length - 1]?.timestamp ?? messages[0]?.timestamp;

  return (
    <div className="flex gap-3 mb-4">
      <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-(--color-secondary)">
        <Bot size={16} />
      </div>
      <div className="max-w-[70%] min-w-0 rounded-2xl bg-(--color-secondary) rounded-tl-sm overflow-hidden">
        {messages.map((msg, i) => {
          const defaultExpanded = shouldDefaultExpand(msg, isStreaming);
          const userToggled = collapsedSections.has(msg.id);
          const isExpanded = userToggled ? !defaultExpanded : defaultExpanded;
          return (
            <GroupSection
              key={msg.id}
              msg={msg}
              isExpanded={isExpanded}
              onToggle={() => onToggleSection(msg.id)}
              showDivider={i > 0}
            />
          );
        })}
        <div className="px-4 py-1">
          <span className="text-[10px] text-(--color-muted-foreground)">
            {new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
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
  const loadAgentSessions = useAppStore((s) => s.loadAgentSessions);
  const agentSessions = useAppStore((s) => s.agentSessions[selectedAgent?.name || ""]) || EMPTY_SESSIONS;
  const switchSession = useAppStore((s) => s.switchSession);
  const createNewSession = useAppStore((s) => s.createNewSession);
  const loadAgentMessages = useAppStore((s) => s.loadAgentMessages);

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const subscribedAgentRef = useRef<string | null>(null);
  const streamBufferRef = useRef("");
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(1000);
  const MAX_RECONNECT_DELAY = 30000;

  const [humanQuestion, setHumanQuestion] = useState<string | null>(null);
  const [humanAnswer, setHumanAnswer] = useState("");
  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const sessionDropdownRef = useRef<HTMLDivElement>(null);

  // Track which sections the user has manually collapsed.
  // When a section is in this set, its default expand/collapse state is flipped.
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const toggleSection = (id: string) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => { scrollToBottom(); }, [selectedAgent?.messages, humanQuestion]);

  // ── Persistent WS connection (mount once) ──
  // Track whether the component is still mounted to avoid Strict Mode
  // double-mount from tearing down and re-creating the WebSocket.
  const mountedRef = useRef(false);
  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    let stopped = false;
    let ws: WebSocket | null = null;

    function connect() {
      if (stopped || !mountedRef.current) return;
      ws = createChatWs();
      wsRef.current = ws;

      ws.onopen = () => {
        if (stopped || !mountedRef.current) {
          ws?.close();
          return;
        }
        reconnectDelayRef.current = 1000;  // reset backoff on successful connection
        const name = useAppStore.getState().activeAgentName;
        if (name) {
          subscribedAgentRef.current = name;
          ws!.send(JSON.stringify({ type: "switch_agent", agent_name: name }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const chunk = JSON.parse(event.data);
          const name = subscribedAgentRef.current;
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
              updatedMsgs[updatedMsgs.length - 1] = {
                ...updatedMsgs[updatedMsgs.length - 1],
                content: streamBufferRef.current,
              };
              flushSync(() => {
                state.updateAgent(name, { messages: updatedMsgs });
              });
            } else {
              flushSync(() => {
                state.addMessage(name, {
                  id: crypto.randomUUID(),
                  role: "assistant",
                  content: chunk.content,
                  timestamp: Date.now(),
                  messageId: chunk.message_id,
                });
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
            // Only end streaming when the agent turn is truly finished.
            // stop_reason "tool_use" means the agent will continue with another
            // model call after executing tools.
            if (chunk.content?.stop_reason === "end_turn") {
              setIsStreaming(name, false);
            }
          } else if (chunk.type === "interrupted") {
            streamBufferRef.current = "";
            setIsStreaming(name, false);
          } else if (chunk.type === "agent_state") {
            setAgentState(name, chunk.state);
            if (chunk.state !== "running") {
              setIsStreaming(name, false);
            }
          } else if (chunk.type === "switched") {
            setAgentState(name, chunk.agent_state);
            if (chunk.agent_state !== "running") {
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
          } else {
            console.log("[WS] unhandled chunk type:", chunk.type, "content:", typeof chunk.content);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        if (stopped || !mountedRef.current) return;
        const name = subscribedAgentRef.current;
        if (name) {
          useAppStore.getState().setIsStreaming(name, false);
        }
        // Schedule reconnect with exponential backoff
        reconnectTimerRef.current = setTimeout(() => {
          connect();
          reconnectDelayRef.current = Math.min(
            reconnectDelayRef.current * 2,
            MAX_RECONNECT_DELAY,
          );
        }, reconnectDelayRef.current);
      };
    }

    connect();

    return () => {
      stopped = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (ws) {
        ws.onclose = null;  // prevent reconnect trigger on intentional close
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
        // If CONNECTING, leave it — onopen will see stopped=true and self-close.
        // This avoids the Strict Mode warning in dev.
      }
    };
  }, []);  // empty deps — once per component mount

  // ── Agent switch: load history FIRST, then send switch_agent ──
  useEffect(() => {
    if (!selectedAgent) return;
    const name = selectedAgent.name;

    // CRITICAL: clear stream buffer AND streaming state on agent switch.
    // In the old per-agent-WS design, closing the old WS triggered onclose
    // which cleared isStreaming. With the persistent WS, onclose never fires
    // on tab switch, so isStreaming would stay stuck at true if the agent
    // completed while the user was away (completed_message is never received).
    streamBufferRef.current = "";
    setIsStreaming(name, false);
    setCollapsedSections(new Set());

    // Load history BEFORE subscribing to WS replay.
    // loadAgentMessages() replaces the entire message list — if replay chunks
    // arrive before HTTP completes, they will be wiped by the replacement.
    const init = async () => {
      await loadAgentMessages(name);
      loadAgentSessions(name);

      // Only send switch_agent if we're not already subscribed to this agent
      if (subscribedAgentRef.current !== name && wsRef.current?.readyState === WebSocket.OPEN) {
        subscribedAgentRef.current = name;
        wsRef.current.send(JSON.stringify({ type: "switch_agent", agent_name: name }));
      }
    };
    init();
  }, [selectedAgent?.name]);

  // ── Session switch: reload messages only (no WS switch needed) ──
  useEffect(() => {
    if (!selectedAgent) return;
    streamBufferRef.current = "";
    setIsStreaming(selectedAgent.name, false);
    setCollapsedSections(new Set());
    loadAgentMessages(selectedAgent.name);
  }, [selectedAgent?.currentSessionId]);

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
    // Show the interrupt button immediately, even before the first text chunk arrives.
    setIsStreaming(selectedAgent.name, true);

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
    // Ignore Enter during IME composition (e.g. confirming Chinese characters).
    if (e.nativeEvent.isComposing) return;
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
      <div className="flex-1 flex flex-col items-center justify-center bg-(--color-background) text-(--color-muted-foreground)">
        <Bot size={48} className="mb-4 opacity-30" />
        <p className="text-lg font-medium">No agent selected</p>
        <p className="text-sm mt-1">Select an agent to start chatting</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-(--color-background)">
      <header className="px-6 py-4 bg-white border-b border-(--color-border)">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-(--color-primary)/10 flex items-center justify-center">
            <Bot size={20} className="text-(--color-primary)" />
          </div>
          <div className="flex-1">
            <h2 className="font-semibold text-(--color-foreground)">{selectedAgent.name}</h2>
            <p className="text-xs text-(--color-muted-foreground)">
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
              className="flex items-center gap-1 px-3 py-1.5 text-xs rounded-lg border border-(--color-border) hover:bg-(--color-secondary) transition-colors"
            >
              <span className="max-w-[120px] truncate">
                {currentSessionId ? currentSessionId.substring(0, 19) : "No session"}
              </span>
              <ChevronDown size={12} />
            </button>
            {sessionDropdownOpen && (
              <div className="absolute right-0 top-full mt-1 w-64 bg-white rounded-lg shadow-lg border border-(--color-border) z-50 max-h-60 overflow-y-auto">
                {agentSessions.map((s: SessionInfo) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      switchSession(selectedAgent.name, s.id);
                      setSessionDropdownOpen(false);
                    }}
                    className={cn(
                      "w-full text-left px-3 py-2 text-xs hover:bg-(--color-secondary) transition-colors",
                      s.isActive && "bg-(--color-primary)/10 text-(--color-primary)"
                    )}
                  >
                    <div className="font-medium truncate">{s.id.substring(0, 19)}</div>
                    <div className="text-(--color-muted-foreground)">
                      {s.turnCount} turns {s.isActive && "(active)"}
                    </div>
                  </button>
                ))}
                {agentSessions.length === 0 && (
                  <div className="px-3 py-2 text-xs text-(--color-muted-foreground)">No sessions found</div>
                )}
                <div className="border-t border-(--color-border)">
                  <button
                    onClick={() => {
                      createNewSession(selectedAgent.name);
                      setSessionDropdownOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-(--color-primary) hover:bg-(--color-secondary) flex items-center gap-1"
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
          <div className="h-full flex flex-col items-center justify-center text-(--color-muted-foreground)">
            <div className="w-16 h-16 rounded-full bg-(--color-secondary) flex items-center justify-center mb-4"><Bot size={28} /></div>
            <p className="text-sm">Start a conversation</p>
            <p className="text-xs mt-1">Send a message to begin</p>
          </div>
        ) : (
          buildSegments(selectedAgent.messages).map((seg) => {
            if (seg.length === 1 && isStandalone(seg[0])) {
              return <MessageBubble key={seg[0].id} message={seg[0]} />;
            }
            return (
              <MessageGroup
                key={`group-${seg[0].id}`}
                messages={seg}
                isStreaming={isStreaming}
                collapsedSections={collapsedSections}
                onToggleSection={toggleSection}
              />
            );
          })
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
        <div className="p-4 bg-white border-t border-(--color-border)">
          <div className="flex items-center gap-3">
            <div className="flex-1 relative">
              <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Type a message..." rows={1}
                className={cn("w-full px-4 py-3 rounded-xl border border-(--color-border)", "bg-(--color-background) resize-none", "focus:outline-none focus:ring-2 focus:ring-(--color-ring) focus:border-transparent", "placeholder:text-(--color-muted-foreground)")}
                style={{ minHeight: "48px", maxHeight: "120px" }} />
            </div>
            {isStreaming ? (
              <button onClick={handleInterrupt}
                className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 border border-(--color-border) bg-red-500 text-white transition-all duration-200 hover:opacity-90">
                <Square size={16} fill="currentColor" />
              </button>
            ) : (
              <button onClick={handleSend} disabled={!input.trim() || agentState === "ready" || agentState === "error"}
                className={cn("w-12 h-12 rounded-xl flex items-center justify-center shrink-0 border border-(--color-border)", "bg-(--color-primary) text-(--color-primary-foreground)", "transition-all duration-200", "hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed")}>
                <Send size={18} />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
