import { useState, useRef, useEffect, Component } from "react";
import { flushSync } from "react-dom";
import { Send, Bot, User, Square, ChevronDown, ChevronRight, Plus, Timer } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Highlight, themes } from "prism-react-renderer";
import { useAppStore, useSelectedAgent, useAgentModel } from "../store";
import { cn } from "../lib/utils";
import { createChatWs } from "../lib/api";
import type { Message, SessionInfo } from "../types";
import { TimerPanel } from "./TimerPanel";

// ── Markdown content renderer for text messages ──
function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        p: ({ children }) => <p className="text-sm leading-relaxed">{children}</p>,
        table: ({ children }) => (
          <div className="overflow-x-auto my-2">
            <table className="min-w-full border-collapse border border-(--color-border) rounded-lg">
              {children}
            </table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border border-(--color-border) px-3 py-1.5 bg-(--color-muted) text-xs font-semibold">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border border-(--color-border) px-3 py-1.5 text-xs">{children}</td>
        ),
        code: ({ className, children, ...props }) => {
          const inline = !className;
          if (inline) {
            return (
              <code className="px-1 py-0.5 rounded bg-gray-100 text-rose-700 text-xs font-mono" {...props}>
                {children}
              </code>
            );
          }
          return (
            <Highlight
              code={String(children).replace(/\n$/, "")}
              language={(className || "").replace("language-", "") || "text"}
              theme={themes.vsLight}
            >
              {({ className: cls, style, tokens, getLineProps, getTokenProps }) => (
                <pre
                  className={cn("text-xs font-mono rounded-lg p-3 my-2 overflow-x-auto", cls)}
                  style={style}
                >
                  {tokens.map((line, i) => (
                    <div key={i} {...getLineProps({ line })}>
                      {line.map((token, key) => (
                        <span key={key} {...getTokenProps({ token })} />
                      ))}
                    </div>
                  ))}
                </pre>
              )}
            </Highlight>
          );
        },
        ul: ({ children }) => <ul className="list-disc pl-5 my-1 text-sm">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal pl-5 my-1 text-sm">{children}</ol>,
        li: ({ children }) => <li className="my-0.5">{children}</li>,
        a: ({ href, children }) => (
          <a href={href} className="text-(--color-primary) underline hover:opacity-80" target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
        h1: ({ children }) => <h1 className="text-lg font-bold mt-3 mb-1">{children}</h1>,
        h2: ({ children }) => <h2 className="text-base font-bold mt-2 mb-1">{children}</h2>,
        h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
        h4: ({ children }) => <h4 className="text-sm font-semibold mt-1 mb-0.5">{children}</h4>,
        blockquote: ({ children }) => (
          <blockquote className="border-l-3 border-(--color-primary)/30 pl-3 my-2 text-sm text-(--color-muted-foreground) italic">
            {children}
          </blockquote>
        ),
        hr: () => <hr className="my-2 border-(--color-border)" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

const EMPTY_SESSIONS: SessionInfo[] = [];

// ── Error boundary: fall back to plain text if markdown parsing throws ──
class SafeMarkdown extends Component<{ content: string }> {
  state = { error: false, prevContent: "" };

  static getDerivedStateFromError() {
    return { error: true };
  }

  componentDidUpdate(prevProps: { content: string }) {
    // Reset error state when content changes (streaming continues)
    if (prevProps.content !== this.props.content && this.state.error) {
      this.setState({ error: false });
    }
  }

  render() {
    if (this.state.error) {
      return <p className="text-sm leading-relaxed whitespace-pre-wrap">{this.props.content}</p>;
    }
    return <MarkdownContent content={this.props.content} />;
  }
}

// ── Standalone message bubble (user message or system notification) ──
function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isSystemNotification = message.role === "system" && !message.chunkType;
  const isInputEvent = message.chunkType === "input_event";

  if (isUser) {
    return (
      <div className="flex gap-3 mb-4 flex-row-reverse">
        <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-(--color-primary) text-(--color-primary-foreground)">
          <User size={16} />
        </div>
        <div className="max-w-[70%]">
          {isInputEvent && message.sourceAgent && (
            <div className="text-right mb-0.5">
              <span className="inline-block text-[10px] font-medium px-2 py-0.5 rounded-full bg-(--color-muted) text-(--color-muted-foreground)">
                {message.sourceAgent}
              </span>
            </div>
          )}
          <div className="rounded-2xl px-4 py-2.5 bg-(--color-primary) text-(--color-primary-foreground) rounded-tr-sm">
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
            <span className="text-[10px] mt-1 block text-(--color-primary-foreground)/60">
              {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            </span>
          </div>
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
        <SafeMarkdown content={message.content} />
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

function shouldDefaultExpand(msg: Message, isStreamingGroup: boolean): boolean {
  // Text and standalone assistant messages are always visible.
  if (!msg.chunkType || msg.chunkType === "text") return true;
  // Non-text blocks (thinking, tool_use, tool_result) auto-expand only if
  // this group is currently being streamed into.
  if (isStreamingGroup) return true;
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
        <SafeMarkdown content={msg.content} />
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
  messages, isRunning, streamingMsgId, collapsedSections, onToggleSection,
}: {
  messages: Message[]; isRunning: boolean; streamingMsgId: string | null;
  collapsedSections: Set<string>; onToggleSection: (id: string) => void;
}) {
  const timestamp = messages[messages.length - 1]?.timestamp ?? messages[0]?.timestamp;
  // Only consider this group "currently streaming" when the agent is running
  // AND one of its messages is the active streaming target.
  const isStreamingGroup = isRunning && messages.some((m) => m.id === streamingMsgId);

  return (
    <div className="flex gap-3 mb-4">
      <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-(--color-secondary)">
        <Bot size={16} />
      </div>
      <div className="max-w-[70%] min-w-0 rounded-2xl bg-(--color-secondary) rounded-tl-sm overflow-hidden">
        {messages.map((msg, i) => {
          const defaultExpanded = shouldDefaultExpand(msg, isStreamingGroup);
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
  const patchMessage = useAppStore((s) => s.patchMessage);
  const agentState = useAppStore((s) => s.agentStates[selectedAgent?.id || ""] || selectedAgent?.state || "ready");
  const isRunning = agentState === "running";
  const setAgentState = useAppStore((s) => s.setAgentState);
  const loadAgentSessions = useAppStore((s) => s.loadAgentSessions);
  const agentSessions = useAppStore((s) => s.agentSessions[selectedAgent?.id || ""]) || EMPTY_SESSIONS;
  const switchSession = useAppStore((s) => s.switchSession);
  const createNewSession = useAppStore((s) => s.createNewSession);
  const loadAgentMessages = useAppStore((s) => s.loadAgentMessages);

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const subscribedAgentRef = useRef<string | null>(null);
  const streamBufferRef = useRef("");
  const currentAssistantMsgIdRef = useRef<string | null>(null);
  const thinkingBufferRef = useRef("");
  const currentThinkingMsgIdRef = useRef<string | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(1000);
  const MAX_RECONNECT_DELAY = 30000;

  const [sessionDropdownOpen, setSessionDropdownOpen] = useState(false);
  const sessionDropdownRef = useRef<HTMLDivElement>(null);

  const [timerPanelOpen, setTimerPanelOpen] = useState(false);
  const agentTimers = useAppStore((s) => s.agentTimers[selectedAgent?.id || ""]) || [];
  const loadTimers = useAppStore((s) => s.loadTimers);

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
  useEffect(() => { scrollToBottom(); }, [selectedAgent?.messages]);

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
        const id = useAppStore.getState().activeAgentId;
        if (id) {
          subscribedAgentRef.current = id;
          ws!.send(JSON.stringify({ type: "switch_agent", agent_name: id }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const chunk = JSON.parse(event.data);
          const agentId = subscribedAgentRef.current;

          // Global dispatcher events (agent_state with agent_id) are
          // always processed — they carry their own target agent id.
          if (chunk.type === "agent_state") {
            setAgentState(chunk.agent_id || agentId, chunk.state);
            return;
          }

          if (!agentId) return;

          if (chunk.type === "text" && chunk.content) {
            streamBufferRef.current += chunk.content;
            const state = useAppStore.getState();
            const currentMsgs = state.agents.find((a) => a.id === agentId)?.messages || [];
            const existingMsg = currentAssistantMsgIdRef.current
              ? currentMsgs.find((m) => m.id === currentAssistantMsgIdRef.current)
              : null;
            if (existingMsg) {
              flushSync(() => patchMessage(agentId, currentAssistantMsgIdRef.current!, { content: streamBufferRef.current }));
            } else {
              const newId = chunk.message_id || crypto.randomUUID();
              currentAssistantMsgIdRef.current = newId;
              flushSync(() => addMessage(agentId, {
                id: newId,
                role: "assistant",
                content: streamBufferRef.current,
                timestamp: Date.now(),
              }));
            }
          } else if (chunk.type === "thinking" && chunk.content) {
            thinkingBufferRef.current += chunk.content;
            const state = useAppStore.getState();
            const currentMsgs = state.agents.find((a) => a.id === agentId)?.messages || [];
            const existingMsg = currentThinkingMsgIdRef.current
              ? currentMsgs.find((m) => m.id === currentThinkingMsgIdRef.current)
              : null;
            if (existingMsg) {
              flushSync(() => patchMessage(agentId, currentThinkingMsgIdRef.current!, { content: thinkingBufferRef.current }));
            } else {
              const newId = crypto.randomUUID();
              currentThinkingMsgIdRef.current = newId;
              flushSync(() => addMessage(agentId, {
                id: newId,
                role: "system",
                content: thinkingBufferRef.current,
                timestamp: Date.now(),
                chunkType: "thinking",
              }));
            }
          } else if (chunk.type === "completed_tool_use") {
            addMessage(agentId, {
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
                addMessage(agentId, {
                  id: crypto.randomUUID(),
                  role: "system",
                  content: typeof r === "string" ? r : JSON.stringify(r),
                  timestamp: Date.now(),
                  chunkType: "tool_result",
                  toolName: r.name || "",
                });
              }
            }
          } else if (chunk.type === "input_event") {
            // Non-direct-user input events (timer, team agent, team user)
            const sourceId: string = chunk.source_id || "";
            let sourceTag: string;
            if (chunk.event_type === "timer_trigger") {
              sourceTag = `Timer: ${sourceId.replace("timer:", "")}`;
            } else if (sourceId.startsWith("team:")) {
              const sender = sourceId.slice(5);
              sourceTag = sender === "user" ? "" : sender;
            } else if (sourceId) {
              sourceTag = sourceId;
            } else {
              sourceTag = chunk.event_type || "";
            }
            addMessage(agentId, {
              id: crypto.randomUUID(),
              role: "user",
              content: chunk.content,
              timestamp: Date.now(),
              chunkType: "input_event",
              sourceAgent: sourceTag || undefined,
            });
          } else if (chunk.type === "completed_message") {
            streamBufferRef.current = "";
            currentAssistantMsgIdRef.current = null;
            thinkingBufferRef.current = "";
            currentThinkingMsgIdRef.current = null;
          } else if (chunk.type === "interrupted") {
            streamBufferRef.current = "";
            currentAssistantMsgIdRef.current = null;
            thinkingBufferRef.current = "";
            currentThinkingMsgIdRef.current = null;
          } else if (chunk.type === "switched") {
            setAgentState(agentId, chunk.agent_state);
          } else if (chunk.type === "error") {
            addMessage(agentId, {
              id: crypto.randomUUID(),
              role: "system",
              content: `Error: ${chunk.content}`,
              timestamp: Date.now(),
              chunkType: "error",
            });
          } else {
            console.log("[WS] unhandled chunk type:", chunk.type, "content:", typeof chunk.content);
          }
        } catch {
          // ignore parse errors
        }
      };

      ws.onclose = () => {
        if (stopped || !mountedRef.current) return;
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
    const id = selectedAgent.id;

    // Clear stream buffer on agent switch. Agent state will be set by
    // the switched chunk (which reads agent.state directly from backend).
    streamBufferRef.current = "";
    currentAssistantMsgIdRef.current = null;
    thinkingBufferRef.current = "";
    currentThinkingMsgIdRef.current = null;
    setCollapsedSections(new Set());

    // Load history BEFORE subscribing to WS replay.
    // loadAgentMessages() replaces the entire message list — if replay chunks
    // arrive before HTTP completes, they will be wiped by the replacement.
    const init = async () => {
      await loadAgentMessages(id);
      loadAgentSessions(id);
      loadTimers(id);

      // Only send switch_agent if we're not already subscribed to this agent
      if (subscribedAgentRef.current !== id && wsRef.current?.readyState === WebSocket.OPEN) {
        subscribedAgentRef.current = id;
        wsRef.current.send(JSON.stringify({
          type: "switch_agent",
          agent_id: id,
          agent_name: name,
        }));
      }
    };
    init();
  }, [selectedAgent?.id]);

  // ── Session switch: reload messages only (no WS switch needed) ──
  useEffect(() => {
    if (!selectedAgent) return;
    streamBufferRef.current = "";
    currentAssistantMsgIdRef.current = null;
    thinkingBufferRef.current = "";
    currentThinkingMsgIdRef.current = null;
    setCollapsedSections(new Set());
    loadAgentMessages(selectedAgent.id);
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
    addMessage(selectedAgent.id, userMessage);

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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Ignore Enter during IME composition (e.g. confirming Chinese characters).
    if (e.nativeEvent.isComposing) return;
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (isRunning) {
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
    <>
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
                agentState === "waiting" && "bg-green-500",
                agentState === "running" && "animate-pulse-green-yellow",
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
                      switchSession(selectedAgent.id, s.id);
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
                      createNewSession(selectedAgent.id);
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
                isRunning={isRunning}
                streamingMsgId={currentAssistantMsgIdRef.current || currentThinkingMsgIdRef.current}
                collapsedSections={collapsedSections}
                onToggleSection={toggleSection}
              />
            );
          })
        )}
        <div ref={messagesEndRef} />
      </div>
      {timerPanelOpen && selectedAgent && (
        <TimerPanel agentId={selectedAgent.id} />
      )}
      <div className="p-4 bg-white border-t border-(--color-border)">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setTimerPanelOpen((v) => !v)}
            className={cn(
              "flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-lg border transition-colors shrink-0",
              timerPanelOpen
                ? "border-(--color-primary) text-(--color-primary) bg-(--color-primary)/10"
                : "border-(--color-border) text-(--color-muted-foreground) hover:bg-(--color-secondary)"
            )}
            title="Timers"
          >
            <Timer size={14} />
            {agentTimers.length > 0 && (
              <span className="font-medium">{agentTimers.length}</span>
            )}
          </button>
          <div className="flex-1 relative">
            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Type a message..." rows={1}
              className={cn("w-full px-4 py-3 rounded-xl border border-(--color-border)", "bg-(--color-background) resize-none", "focus:outline-none focus:ring-2 focus:ring-(--color-ring) focus:border-transparent", "placeholder:text-(--color-muted-foreground)")}
              style={{ minHeight: "48px", maxHeight: "120px" }} />
          </div>
          {isRunning ? (
            <button onClick={handleInterrupt}
              className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 border border-(--color-border) bg-red-500 text-white transition-all duration-200 hover:opacity-90">
              <Square size={16} fill="currentColor" />
            </button>
          ) : (
            <button onClick={handleSend} disabled={!input.trim() || agentState !== "waiting"}
              className={cn("w-12 h-12 rounded-xl flex items-center justify-center shrink-0 border border-(--color-border)", "bg-(--color-primary) text-(--color-primary-foreground)", "transition-all duration-200", "hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed")}>
              <Send size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
    </>
  );
}
