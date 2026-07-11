import { useState, useRef, useEffect, useMemo, memo, Component } from "react";
import { flushSync } from "react-dom";
import { Bot, User, Square, ChevronDown, ChevronRight, Plus, Timer, Sparkles, ArrowUp, Terminal, Brain, Wrench, FileText, ListTodo, Paperclip, X } from "lucide-react";
import { useAppStore, useSelectedAgent, useAgentModel } from "../store";
import { cn } from "../lib/utils";
import { api } from "../lib/api";
import type { AttachmentInfo, Message, SessionInfo } from "../types";
import { TimerPanel } from "./TimerPanel";
import { MarkdownContent } from "./MarkdownContent";

// ── Turn dots navigation ──
const TurnDots = memo(function TurnDots({
  turns,
  scrollContainerRef,
}: {
  turns: Message[];
  scrollContainerRef: React.RefObject<HTMLDivElement | null>;
}) {
  const [activeIndex, setActiveIndex] = useState(-1);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [tooltipVisible, setTooltipVisible] = useState(false);
  const navRef = useRef<HTMLDivElement>(null);

  // use IntersectionObserver to track turns in the visible area (replaces scroll event O(n) DOM queries)
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el || turns.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        let closestIdx = -1;
        let minDist = Infinity;
        const containerRect = el.getBoundingClientRect();

        for (const entry of entries) {
          if (entry.isIntersecting) {
            const idx = turns.findIndex((t) => t.id === entry.target.getAttribute('data-message-id'));
            if (idx !== -1) {
              const dist = Math.abs(entry.boundingClientRect.top - containerRect.top - 60);
              if (dist < minDist) {
                minDist = dist;
                closestIdx = idx;
              }
            }
          }
        }
        if (closestIdx !== -1) {
          setActiveIndex(closestIdx);
        }
      },
      { root: el, rootMargin: '-60px 0px 0px 0px', threshold: 0 }
    );

    // observe all turn elements
    const targets: Element[] = [];
    for (let i = 0; i < turns.length; i++) {
      const turnEl = el.querySelector(`[data-message-id="${turns[i].id}"]`);
      if (turnEl) {
        observer.observe(turnEl);
        targets.push(turnEl);
      }
    }

    // initial calculation
    requestAnimationFrame(() => {
      const containerRect = el.getBoundingClientRect();
      for (let i = 0; i < turns.length; i++) {
        const turnEl = targets[i];
        if (!turnEl) continue;
        const rect = turnEl.getBoundingClientRect();
        const dist = Math.abs(rect.top - containerRect.top - 60);
        if (dist < 60) {
          setActiveIndex(i);
          break;
        }
      }
    });

    return () => {
      observer.disconnect();
    };
  }, [scrollContainerRef, turns]);

  const scrollToTurn = (index: number) => {
    const el = scrollContainerRef.current?.querySelector(
      `[data-message-id="${turns[index].id}"]`
    );
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const previewText = (msg: Message) => {
    const text = msg.content || "";
    return text.length > 50 ? text.slice(0, 50) + "…" : text;
  };

  if (turns.length < 2) return null;

  return (
    <div ref={navRef} className="w-10 shrink-0 flex flex-col items-center pt-4">
      <div className="sticky top-[100px] flex flex-col items-center gap-1.5">
        {turns.map((turn, i) => {
          const dotClass = cn(
            "w-2 h-2 rounded-full transition-all cursor-pointer",
            i === activeIndex
              ? "bg-(--color-primary) scale-125"
              : "bg-(--color-border) hover:bg-(--color-ink-3)"
          );

          return (
            <div
              key={turn.id}
              className="relative flex items-center justify-center w-6 h-6 group"
              onMouseEnter={() => {
                setHoveredIndex(i);
                setTooltipVisible(true);
              }}
              onMouseLeave={() => {
                setHoveredIndex(null);
                setTooltipVisible(false);
              }}
            >
              <div
                className={dotClass}
                onClick={() => scrollToTurn(i)}
                title={`Turn ${i + 1}`}
              />

              {/* Tooltip */}
              {hoveredIndex === i && tooltipVisible && (
                <div className="absolute right-full mr-2 top-1/2 -translate-y-1/2 z-50">
                  <div className="bg-(--color-foreground) text-(--color-background) text-[11px] leading-[1.4] rounded-md px-2.5 py-1.5 max-w-[200px] shadow-lg whitespace-normal break-words">
                    <span className="font-semibold text-[10px] opacity-60">#{i + 1}</span>
                    <p className="mt-0.5">{previewText(turn)}</p>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
});

const EMPTY_SESSIONS: SessionInfo[] = [];
const EMPTY_MESSAGES: Message[] = [];
const EMPTY_COLLAPSED_SECTIONS = new Set<string>();
const INITIAL_VISIBLE_SEGMENTS = 80;
const SEGMENT_PAGE_SIZE = 80;

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function formatAttachmentSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function formatMessageWithAttachments(content: string, attachments: AttachmentInfo[]): string {
  if (attachments.length === 0) return content;
  const lines = attachments.map(
    (attachment) =>
      `- ${attachment.originalName}: file_id=${attachment.id} (${attachment.contentType}, ${attachment.size} bytes)`
  );
  return [
    content || "Please review the uploaded file(s).",
    "",
    "[Files]",
    "These files were uploaded by the user and copied into managed local storage. Use read_file with file_id when needed:",
    ...lines,
  ].join("\n");
}

// ── Error boundary: fall back to plain text if markdown parsing throws ──
const SafeMarkdown = memo(class SafeMarkdown extends Component<{ content: string; isStreaming?: boolean }> {
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
      return <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{this.props.content}</p>;
    }
    return <MarkdownContent content={this.props.content} isStreaming={this.props.isStreaming} />;
  }
});

// ── Single turn block (Apple-style: no bubble, avatar + name + content) ──
const TurnBlock = memo(function TurnBlock({ message }: { message: Message }) {
  const isInputEvent = message.chunkType === "input_event";
  const isRealUser = message.role === "user" && !message.sourceAgent;
  const isSystemNotification = message.role === "system" && !message.chunkType;
  const ts = new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  if (isSystemNotification) {
    return (
      <div className="px-8 py-2 flex justify-center">
        <span className="text-[11.5px] text-(--color-ink-3)">
          {message.content}
        </span>
      </div>
    );
  }

  const displayName = isRealUser ? "You" : isInputEvent && message.sourceAgent ? message.sourceAgent : "Assistant";

  return (
    <div className="py-5 w-full" data-message-id={message.id}>
      <div className="mx-4 pb-5 border-b border-(--color-rule-soft) flex gap-3">
        <div
          className={cn(
            "w-[22px] h-[22px] rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0 mt-0.5",
            isRealUser
              ? "bg-(--color-foreground) text-white"
              : "bg-gradient-to-br from-(--color-primary) to-blue-500 text-white"
          )}
        >
          {isRealUser ? <User size={11} /> : <Sparkles size={11} />}
        </div>
        <div className="flex-1 min-w-0 overflow-x-clip">
          <div className="flex items-baseline gap-2 mb-1.5">
            <span className="text-[12.5px] font-semibold text-(--color-foreground)">
              {displayName}
            </span>
            <span className="text-[11px] text-(--color-ink-3) tabular-nums">
              {ts}
            </span>
          </div>
          {isInputEvent && message.sourceAgent && (
            <div className="mb-1">
              <span className="inline-block text-[10px] font-medium px-2 py-0.5 rounded-full bg-(--color-secondary) text-(--color-ink-2)">
                {message.sourceAgent}
              </span>
            </div>
          )}
          <div className="text-[14.5px] leading-[1.6] text-(--color-foreground) tracking-[-0.005em] min-w-0 break-words">
            {isRealUser ? (
              <p className="whitespace-pre-wrap break-words [overflow-wrap:anywhere] min-w-0">{message.content}</p>
            ) : (
              <SafeMarkdown content={message.content} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

// ── Grouping helpers ──

function sectionLabel(msg: Message): string {
  switch (msg.chunkType) {
    case "thinking": return "Thinking";
    case "tool_use": return `Calling: ${msg.toolName || ""}`;
    case "tool_result": return `Result: ${msg.toolName || ""}`;
    case "todo_list": return "Todo list";
    case "error": return "Error";
    default: return "";
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

// ── A single collapsible section within a message group (Apple: header bar) ──
const GroupSection = memo(function GroupSection({
  msg, isExpanded, onToggle, showDivider, isStreaming = false,
}: {
  msg: Message; isExpanded: boolean; onToggle: () => void; showDivider: boolean; isStreaming?: boolean;
}) {
  const label = sectionLabel(msg);
  const isText = !msg.chunkType || msg.chunkType === "text";

  if (isText) {
    return (
      <div className={showDivider ? "mt-2" : ""}>
        <SafeMarkdown content={msg.content} isStreaming={isStreaming} />
      </div>
    );
  }

  // ── Thinking: italic label + Brain icon, keep gray tones but distinguish with dashed border ──
  if (msg.chunkType === "thinking") {
    return (
      <div className={cn("my-2 rounded-lg border border-dashed border-(--color-border) bg-(--color-tint) min-w-0", showDivider && "mt-2")}>
        <button
          onClick={onToggle}
          className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-(--color-secondary)/60 transition-colors"
        >
          <Brain size={12} className="text-(--color-ink-3) shrink-0" />
          <span className="text-[11.5px] italic text-(--color-ink-3) tracking-tight">Thinking</span>
          <span className="ml-auto text-(--color-ink-3) shrink-0">
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
        </button>
        {isExpanded && (
          <div className="border-t border-dashed border-(--color-border) px-3 py-2 overflow-x-auto">
            <pre className="text-[12px] font-mono leading-[1.6] text-(--color-ink-3) whitespace-pre-wrap max-h-60 overflow-y-auto">
              {msg.content}
            </pre>
          </div>
        )}
      </div>
    );
  }

  // ── Tool Use: Wrench icon + tool name highlight + parameter summary ──
  if (msg.chunkType === "tool_use") {
    const toolInput = msg.toolInput || {};
    const inputKeys = Object.keys(toolInput);
    const paramSummary = inputKeys.length > 0
      ? inputKeys.map(k => {
          const v = toolInput[k];
          const vs = typeof v === "string" ? v : JSON.stringify(v, null, 0);
          return vs.length > 50 ? `${k}: ${vs.slice(0, 47)}…` : `${k}: ${vs}`;
        }).join("  ·  ")
      : "";

    return (
      <div className={cn("my-2 rounded-lg border border-(--color-border) bg-(--color-tint) min-w-0", showDivider && "mt-2")}>
        <button
          onClick={onToggle}
          className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-(--color-secondary)/60 transition-colors"
        >
          <Wrench size={12} className="text-(--color-ink-3) shrink-0" />
          <span className="text-[11.5px] font-medium text-(--color-ink-2) font-mono tracking-tight">{msg.toolName || "tool"}</span>
          {paramSummary && !isExpanded && (
            <span className="text-[10.5px] text-(--color-ink-3) truncate max-w-[50%]">{paramSummary}</span>
          )}
          <span className="ml-auto text-(--color-ink-3) shrink-0">
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
        </button>
        {isExpanded && (
          <div className="border-t border-(--color-border) px-3 py-2 overflow-x-auto">
            <pre className="text-[12px] font-mono leading-[1.6] text-(--color-ink-2) whitespace-pre max-h-60 overflow-y-auto">
              {msg.content}
            </pre>
          </div>
        )}
      </div>
    );
  }

  // ── Tool Result: FileText icon + tool name ──
  if (msg.chunkType === "tool_result") {
    const displayContent = msg.content || "";

    return (
      <div className={cn("my-2 rounded-lg border border-(--color-border) bg-(--color-tint)/60 min-w-0", showDivider && "mt-2")}>
        <button
          onClick={onToggle}
          className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-(--color-secondary)/60 transition-colors"
        >
          <FileText size={12} className="text-(--color-ink-3) shrink-0" />
          <span className="text-[11.5px] font-medium text-(--color-ink-2) tracking-tight">Result: {msg.toolName || "tool"}</span>
          {!isExpanded && displayContent.length <= 80 && (
            <span className="text-[10.5px] text-(--color-ink-3) truncate max-w-[50%]">{displayContent}</span>
          )}
          <span className="ml-auto text-(--color-ink-3) shrink-0">
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
        </button>
        {isExpanded && (
          <div className="border-t border-(--color-border) px-3 py-2 overflow-x-auto">
            <pre className="text-[12px] font-mono leading-[1.6] text-(--color-ink-2) whitespace-pre-wrap break-words max-h-60 overflow-y-auto">
              {displayContent}
            </pre>
          </div>
        )}
      </div>
    );
  }

  if (msg.chunkType === "todo_list") {
    const displayContent = msg.content || "";

    return (
      <div className={cn("my-2 rounded-lg border border-(--color-border) bg-(--color-tint)/60 min-w-0", showDivider && "mt-2")}>
        <button
          onClick={onToggle}
          className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-(--color-secondary)/60 transition-colors"
        >
          <ListTodo size={12} className="text-(--color-ink-3) shrink-0" />
          <span className="text-[11.5px] font-medium text-(--color-ink-2) tracking-tight">Todo list</span>
          {!isExpanded && displayContent.length <= 80 && (
            <span className="text-[10.5px] text-(--color-ink-3) truncate max-w-[50%]">{displayContent}</span>
          )}
          <span className="ml-auto text-(--color-ink-3) shrink-0">
            {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
        </button>
        {isExpanded && (
          <div className="border-t border-(--color-border) px-3 py-2 overflow-x-auto">
            <pre className="text-[12px] font-mono leading-[1.6] text-(--color-ink-2) whitespace-pre-wrap break-words max-h-60 overflow-y-auto">
              {displayContent}
            </pre>
          </div>
        )}
      </div>
    );
  }

  // ── Error ──
  return (
    <div className={cn("my-2 rounded-lg border border-(--color-border) bg-(--color-tint) min-w-0", showDivider && "mt-2")}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-(--color-secondary)/60 transition-colors"
      >
        <Terminal size={12} className="text-(--color-ink-3) shrink-0" />
        <span className="text-[11.5px] font-medium text-(--color-ink-2) font-mono tracking-tight">{label}</span>
        <span className="ml-auto text-(--color-ink-3) shrink-0">
          {isExpanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
      </button>
      {isExpanded && (
        <div className="border-t border-(--color-border) px-3 py-2 overflow-x-auto">
          <pre className="text-[12px] font-mono leading-[1.6] text-(--color-ink-2) whitespace-pre max-h-40 overflow-y-auto">
            {msg.content}
          </pre>
        </div>
      )}
    </div>
  );
});

// ── Composite group for adjacent non-user messages (Apple-style no-bubble) ──
const TurnGroup = memo(function TurnGroup({
  messages, isRunning, streamingMsgId, collapsedSections, onToggleSection,
}: {
  messages: Message[]; isRunning: boolean; streamingMsgId: string | null;
  collapsedSections: Set<string>; onToggleSection: (id: string) => void;
}) {
  const timestamp = messages[messages.length - 1]?.timestamp ?? messages[0]?.timestamp;
  const isStreamingGroup = isRunning && messages.some((m) => m.id === streamingMsgId);
  const ts = new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className="py-5 w-full">
      <div className="mx-4 pb-5 border-b border-(--color-rule-soft) flex gap-3">
        <div className="w-[22px] h-[22px] rounded-full bg-gradient-to-br from-(--color-primary) to-blue-500 text-white flex items-center justify-center shrink-0 mt-0.5">
          <Sparkles size={11} />
        </div>
        <div className="flex-1 min-w-0 overflow-x-clip">
          <div className="flex items-baseline gap-2 mb-1.5">
            <span className="text-[12.5px] font-semibold text-(--color-foreground)">Assistant</span>
            <span className="text-[11px] text-(--color-ink-3) tabular-nums">{ts}</span>
          </div>
          <div className="text-[14.5px] leading-[1.6] text-(--color-foreground) tracking-[-0.005em] min-w-0 break-words">
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
                  isStreaming={isStreamingGroup && (msg.id === streamingMsgId)}
                />
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
});

export function ChatWindow() {
  const selectedAgent = useSelectedAgent();
  const agentModel = useAgentModel();
  const addMessage = useAppStore((s) => s.addMessage);
  const upsertMessage = useAppStore((s) => s.upsertMessage);
  const patchMessage = useAppStore((s) => s.patchMessage);
  const agentState = useAppStore((s) => s.agentStates[selectedAgent?.id || ""] || selectedAgent?.state || "ready");
  const isRunning = agentState === "running";
  const sessionActionsDisabled = agentState === "running";
  const setAgentState = useAppStore((s) => s.setAgentState);
  const addToast = useAppStore((s) => s.addToast);
  const contextTokens = useAppStore((s) => s.agentContextTokens[selectedAgent?.id || ""] || 0);
  const loadAgentSessions = useAppStore((s) => s.loadAgentSessions);
  const agentSessions = useAppStore((s) => s.agentSessions[selectedAgent?.id || ""]) || EMPTY_SESSIONS;
  const createNewSession = useAppStore((s) => s.createNewSession);
  const loadAgentMessages = useAppStore((s) => s.loadAgentMessages);
  const sessionPanelOpen = useAppStore((s) => s.sessionPanelOpen);
  const toggleSessionPanel = useAppStore((s) => s.toggleSessionPanel);
  const selectedAgentId = selectedAgent?.id || "";
  const selectedAgentName = selectedAgent?.name || "";
  const selectedSessionId = selectedAgent?.currentSessionId || "";
  const input = useAppStore((s) => (selectedAgentId ? s.agentInputs[selectedAgentId] || "" : ""));
  const setAgentInput = useAppStore((s) => s.setAgentInput);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const subscribedAgentRef = useRef<string | null>(null);
  const streamBufferRef = useRef("");
  const currentAssistantMsgIdRef = useRef<string | null>(null);
  const thinkingBufferRef = useRef("");
  const currentThinkingMsgIdRef = useRef<string | null>(null);
  const textFlushPendingRef = useRef(false);
  const thinkingFlushPendingRef = useRef(false);
  const [streamingMsgId, setStreamingMsgId] = useState<string | null>(null);
  const attachmentScope = `${selectedAgentId}:${selectedSessionId}`;
  const [attachmentState, setAttachmentState] = useState<{ scope: string; items: AttachmentInfo[] }>({
    scope: "",
    items: [],
  });
  const [isUploadingAttachments, setIsUploadingAttachments] = useState(false);
  const [visibleSegmentState, setVisibleSegmentState] = useState({
    scope: "",
    count: INITIAL_VISIBLE_SEGMENTS,
  });

  const [timerPanelOpen, setTimerPanelOpen] = useState(false);
  const agentTimers = useAppStore((s) => s.agentTimers[selectedAgent?.id || ""]) || [];
  const loadTimers = useAppStore((s) => s.loadTimers);

  // Track which sections the user has manually collapsed.
  // When a section is in this set, its default expand/collapse state is flipped.
  const collapsedScope = `${selectedAgentId}:${selectedSessionId}`;
  const [collapsedState, setCollapsedState] = useState<{ scope: string; sections: Set<string> }>({
    scope: "",
    sections: EMPTY_COLLAPSED_SECTIONS,
  });
  const collapsedSections = collapsedState.scope === collapsedScope
    ? collapsedState.sections
    : EMPTY_COLLAPSED_SECTIONS;
  const toggleSection = (id: string) => {
    setCollapsedState((prev) => {
      const current = prev.scope === collapsedScope ? prev.sections : EMPTY_COLLAPSED_SECTIONS;
      const next = new Set(current);
      if (next.has(id)) next.delete(id); else next.add(id);
      return { scope: collapsedScope, sections: next };
    });
  };
  const messages = selectedAgent?.messages || EMPTY_MESSAGES;
  const attachments = attachmentState.scope === attachmentScope ? attachmentState.items : [];

  // extract all turns (each conversation turn starts with a user message or input_event)
  const turns = useMemo(() => {
    return messages.filter(
      (m) => m.role === "user" || m.chunkType === "input_event"
    );
  }, [messages]);

  const segments = useMemo(() => {
    return buildSegments(messages);
  }, [messages]);
  const visibleSegmentScope = `${selectedAgentId}:${selectedSessionId}`;
  const visibleSegmentCount = visibleSegmentState.scope === visibleSegmentScope
    ? visibleSegmentState.count
    : INITIAL_VISIBLE_SEGMENTS;
  const hiddenSegmentCount = Math.max(0, segments.length - visibleSegmentCount);
  const visibleSegments = hiddenSegmentCount > 0 ? segments.slice(hiddenSegmentCount) : segments;

  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const isUserScrollingRef = useRef(false);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "instant" as ScrollBehavior }); };

  // detect if user actively scrolled up
  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    const onScroll = () => {
      const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
      isUserScrollingRef.current = distanceFromBottom > 60;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  // only auto-scroll to bottom when not user-active scrolling
  useEffect(() => {
    if (!isUserScrollingRef.current) scrollToBottom();
  }, [selectedAgent?.messages]);

  // ── register onWsChunk: non-agent_state messages are dispatched uniformly by useGlobalAgentState's shared WS ──

  useEffect(() => {
    const handler = (chunk: Record<string, unknown>) => {
      const agentId = subscribedAgentRef.current;
      if (!agentId) return;

      if (chunk.type === "stream_chunk" && chunk.chunk_type === "text" && chunk.content) {
        const content = chunk.content as string;
        streamBufferRef.current += content;
        const state = useAppStore.getState();
        const currentMsgs = state.agents.find((a) => a.id === agentId)?.messages || [];
        const existingMsg = currentAssistantMsgIdRef.current
          ? currentMsgs.find((m) => m.id === currentAssistantMsgIdRef.current)
          : null;
        if (!existingMsg) {
          const newId = (chunk.message_id as string) || crypto.randomUUID();
          currentAssistantMsgIdRef.current = newId;
          setStreamingMsgId(newId);
          flushSync(() => addMessage(agentId, {
            id: newId,
            role: "assistant",
            content: streamBufferRef.current,
            timestamp: Date.now(),
          }));
        } else if (!textFlushPendingRef.current) {
          textFlushPendingRef.current = true;
          requestAnimationFrame(() => {
            textFlushPendingRef.current = false;
            flushSync(() => patchMessage(agentId, currentAssistantMsgIdRef.current!, { content: streamBufferRef.current }));
          });
        }
      } else if (chunk.type === "stream_chunk" && chunk.chunk_type === "thinking" && chunk.content) {
        const content = chunk.content as string;
        thinkingBufferRef.current += content;
        const state = useAppStore.getState();
        const currentMsgs = state.agents.find((a) => a.id === agentId)?.messages || [];
        const existingMsg = currentThinkingMsgIdRef.current
          ? currentMsgs.find((m) => m.id === currentThinkingMsgIdRef.current)
          : null;
        if (!existingMsg) {
          const newId = crypto.randomUUID();
          currentThinkingMsgIdRef.current = newId;
          setStreamingMsgId(newId);
          flushSync(() => addMessage(agentId, {
            id: newId,
            role: "system",
            content: thinkingBufferRef.current,
            timestamp: Date.now(),
            chunkType: "thinking",
          }));
        } else if (!thinkingFlushPendingRef.current) {
          thinkingFlushPendingRef.current = true;
          requestAnimationFrame(() => {
            thinkingFlushPendingRef.current = false;
            flushSync(() => patchMessage(agentId, currentThinkingMsgIdRef.current!, { content: thinkingBufferRef.current }));
          });
        }
      } else if (chunk.type === "stream_chunk" && chunk.chunk_type === "completed_tool_use") {
        const ct = chunk.content as Record<string, unknown> | undefined;
        const toolCallId = (ct?.id as string) || "";
        upsertMessage(agentId, {
          id: toolCallId ? `tool_use:${toolCallId}` : crypto.randomUUID(),
          role: "system",
          content: JSON.stringify(ct?.input || {}, null, 2),
          timestamp: Date.now(),
          chunkType: "tool_use",
          toolName: (ct?.name as string) || "",
          toolInput: (ct?.input as Record<string, unknown>) || {},
          toolCallId,
          runtime: true,
        });
      } else if (chunk.type === "stream_chunk" && chunk.chunk_type === "tool_results") {
        const results = chunk.content;
        if (Array.isArray(results)) {
          for (const r of results) {
            // ToolMessage after _make_serializable is a dict: {role, id, name, content, timestamp}
            const rDict = r as Record<string, unknown>;
            const toolName = (rDict.name as string) || "";
            const rawContent = rDict.content;
            let contentStr: string;
            if (typeof rawContent === "string") {
              contentStr = rawContent;
            } else if (Array.isArray(rawContent)) {
              const textParts: string[] = [];
              for (const block of rawContent as Record<string, unknown>[]) {
                if (block.type === "text") {
                  textParts.push(block.text as string || "");
                }
              }
              contentStr = textParts.length > 0
                ? textParts.join("\n")
                : JSON.stringify(rawContent, null, 2);
            } else {
              contentStr = JSON.stringify(rawContent, null, 2);
            }
            const toolCallId = (rDict.id as string) || "";
            upsertMessage(agentId, {
              id: toolCallId ? `tool_result:${toolCallId}` : crypto.randomUUID(),
              role: "system",
              content: contentStr,
              timestamp: Date.now(),
              chunkType: "tool_result",
              toolName,
              toolCallId,
              runtime: true,
            });
          }
        }
      } else if (chunk.type === "stream_chunk" && chunk.chunk_type === "todo_list") {
        const snapshot = chunk.content as Record<string, unknown> | undefined;
        if (!snapshot) return;
        const items = Array.isArray(snapshot.items) ? (snapshot.items as Record<string, unknown>[]) : [];
        const groups = {
          inProgress: items.filter((item) => item.status === "in_progress"),
          ready: items.filter((item) => item.status === "pending" && item.ready),
          blocked: items.filter((item) => item.status === "blocked"),
        };
        const lines = [
          "[Current Todo List]",
          `Title: ${String(snapshot.title || "")}`,
        ];
        const renderGroup = (label: string, groupItems: Record<string, unknown>[]) => {
          if (!groupItems.length) return;
          lines.push("");
          lines.push(`${label}:`);
          for (const item of groupItems) {
            lines.push(`- ${String(item.id || "")}: ${String(item.content || "")}`);
            if (Array.isArray(item.blocked_by) && item.blocked_by.length) {
              lines.push(`  blocked_by: ${item.blocked_by.join(", ")}`);
            }
            if (item.notes) {
              lines.push(`  notes: ${String(item.notes)}`);
            }
          }
        };
        renderGroup("In progress", groups.inProgress);
        renderGroup("Ready to work on", groups.ready);
        renderGroup("Blocked", groups.blocked);
        upsertMessage(agentId, {
          id: `todo_list:${String(snapshot.id || crypto.randomUUID())}`,
          role: "system",
          content: lines.join("\n"),
          timestamp: Date.now(),
          chunkType: "todo_list",
          runtime: true,
        });
      } else if (chunk.type === "event" && ["user_input", "timer_input", "agent_input"].includes(chunk.event_type as string)) {
        const sourceId = (chunk.source_id as string) || "";
        const eventType = (chunk.event_type as string) || "";
        if (eventType === "user_input") {
          if (sourceId !== "user") {
            // sourceId is the frontend message_id — upsert for dedup (normal flow)
            // and recovery (dispatcher replay after agent switch wipes history).
            upsertMessage(agentId, {
              id: sourceId,
              role: "user",
              content: chunk.content as string,
              timestamp: Date.now(),
              chunkType: "input_event",
            });
          }
          return;
        }
        let sourceTag: string;
        if (eventType === "timer_input") {
          sourceTag = `Timer: ${sourceId.replace("timer:", "")}`;
        } else if (sourceId.startsWith("team:")) {
          const sender = sourceId.slice(5);
          sourceTag = sender === "user" ? "" : sender;
        } else if (sourceId) {
          sourceTag = sourceId;
        } else {
          sourceTag = eventType || "";
        }
        addMessage(agentId, {
          id: crypto.randomUUID(),
          role: "user",
          content: chunk.content as string,
          timestamp: Date.now(),
          chunkType: "input_event",
          sourceAgent: sourceTag || undefined,
        });
      } else if (chunk.type === "stream_chunk" && chunk.chunk_type === "completed_message") {
        // replace streaming concatenated message with final complete content from completed_message
        const completedMsg = chunk.content as Record<string, unknown> | undefined;
        if (completedMsg && currentAssistantMsgIdRef.current) {
          // extract final text content
          const rawContent = completedMsg.content;
          let finalContent: string;
          if (typeof rawContent === "string") {
            finalContent = rawContent;
          } else if (Array.isArray(rawContent)) {
            const textParts: string[] = [];
            for (const block of rawContent as Record<string, unknown>[]) {
              if (block.type === "text") {
                textParts.push(block.text as string || "");
              }
            }
            finalContent = textParts.join("\n");
          } else {
            finalContent = streamBufferRef.current;
          }
          // replace streaming message with final content (ensure markdown renders completely)
          if (finalContent) {
            flushSync(() => patchMessage(agentId, currentAssistantMsgIdRef.current!, { content: finalContent }));
          }
        }
        streamBufferRef.current = "";
        currentAssistantMsgIdRef.current = null;
        thinkingBufferRef.current = "";
        currentThinkingMsgIdRef.current = null;
        textFlushPendingRef.current = false;
        thinkingFlushPendingRef.current = false;
        setStreamingMsgId(null);
      } else if (chunk.type === "event" && chunk.event_type === "interrupted") {
        streamBufferRef.current = "";
        currentAssistantMsgIdRef.current = null;
        thinkingBufferRef.current = "";
        currentThinkingMsgIdRef.current = null;
        textFlushPendingRef.current = false;
        thinkingFlushPendingRef.current = false;
        setStreamingMsgId(null);
      } else if (chunk.type === "switched") {
        setAgentState(agentId, (chunk.agent_state as "ready" | "waiting" | "running" | "error"));
        if (typeof chunk.context_tokens === "number") {
          useAppStore.getState().setAgentContextTokens(agentId, chunk.context_tokens);
        }
      } else if (chunk.type === "event" && chunk.event_type === "error") {
        addMessage(agentId, {
          id: crypto.randomUUID(),
          role: "system",
          content: `Error: ${chunk.content}`,
          timestamp: Date.now(),
          chunkType: "error",
        });
      }
    };

    useAppStore.setState({ onWsChunk: handler });

    return () => {
      useAppStore.setState({ onWsChunk: null });
    };
  }, [addMessage, upsertMessage, patchMessage, setAgentState]);

  // ── Agent switch: load history FIRST, then send switch_agent ──
  useEffect(() => {
    if (!selectedAgentId) return;
    const name = selectedAgentName;
    const id = selectedAgentId;

    // Clear stream buffer on agent switch. Agent state will be set by
    // the switched chunk (which reads agent.state directly from backend).
    streamBufferRef.current = "";
    currentAssistantMsgIdRef.current = null;
    thinkingBufferRef.current = "";
    currentThinkingMsgIdRef.current = null;
    // Load history BEFORE subscribing to WS replay.
    // loadAgentMessages() replaces the entire message list — if replay chunks
    // arrive before HTTP completes, they will be wiped by the replacement.
    const init = async () => {
      // actively fetch agent's current state to ensure correct state displays immediately after switch
      try {
        const stateInfo = await api.getAgentState(id);
        if (stateInfo?.state) {
          setAgentState(id, stateInfo.state as "ready" | "waiting" | "running" | "error");
        }
      } catch {
        // silent failure, WS switched message will cover it
      }

      await loadAgentMessages(id);
      loadAgentSessions(id);
      loadTimers(id);

      // Only send switch_agent if we're not already subscribed to this agent
      const chatWs = useAppStore.getState().chatWs;
      if (subscribedAgentRef.current !== id && chatWs?.readyState === WebSocket.OPEN) {
        subscribedAgentRef.current = id;
        chatWs.send(JSON.stringify({
          type: "switch_agent",
          agent_id: id,
          agent_name: name,
        }));
      }
    };
    init();
  }, [selectedAgentId, selectedAgentName, loadAgentMessages, loadAgentSessions, loadTimers, setAgentState]);

  // ── Session switch: reload messages only (no WS switch needed) ──
  useEffect(() => {
    if (!selectedAgentId) return;
    streamBufferRef.current = "";
    currentAssistantMsgIdRef.current = null;
    thinkingBufferRef.current = "";
    currentThinkingMsgIdRef.current = null;
    loadAgentMessages(selectedAgentId);
  }, [selectedAgentId, selectedSessionId, loadAgentMessages]);

  const handleFileUpload = async (fileList: FileList | File[]) => {
    if (!selectedAgent) return;
    const files = Array.from(fileList);
    if (files.length === 0) return;

    setIsUploadingAttachments(true);
    try {
      const uploaded = await api.uploadFiles(selectedAgent.id, files) as AttachmentInfo[];
      setAttachmentState((current) => ({
        scope: attachmentScope,
        items: [...(current.scope === attachmentScope ? current.items : []), ...uploaded],
      }));
    } catch (error) {
      addToast(`File upload failed: ${errorMessage(error)}`, "warning");
    } finally {
      setIsUploadingAttachments(false);
    }
  };

  const removeAttachment = (id: string) => {
    setAttachmentState((current) => ({
      scope: attachmentScope,
      items: (current.scope === attachmentScope ? current.items : []).filter((attachment) => attachment.id !== id),
    }));
  };

  const handleSend = () => {
    if (
      (!input.trim() && attachments.length === 0)
      || !selectedAgent
      || isUploadingAttachments
      || agentState !== "waiting"
    ) return;
    const content = input.trim() || "Please review the uploaded file(s).";
    const outgoingAttachments = attachments;
    const displayContent = formatMessageWithAttachments(content, outgoingAttachments);
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: displayContent, timestamp: Date.now() };
    addMessage(selectedAgent.id, userMessage);

    const chatWs = useAppStore.getState().chatWs;
    if (chatWs?.readyState === WebSocket.OPEN) {
      chatWs.send(JSON.stringify({
        type: "user_message",
        content,
        attachments: outgoingAttachments,
        message_id: userMessage.id,
      }));
    }
    setAgentInput(selectedAgent.id, "");
    setAttachmentState({ scope: attachmentScope, items: [] });
  };

  const handleInterrupt = () => {
    const chatWs = useAppStore.getState().chatWs;
    if (chatWs?.readyState === WebSocket.OPEN) {
      chatWs.send(JSON.stringify({ type: "interrupt" }));
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
  const canSend = (input.trim().length > 0 || attachments.length > 0)
    && agentState === "waiting"
    && !isUploadingAttachments;

  if (!selectedAgent) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-(--color-background) text-(--color-ink-2)">
        <Bot size={36} className="mb-3 opacity-40" />
        <p className="text-[15px] font-medium">No agent selected</p>
        <p className="text-[12.5px] mt-1 text-(--color-ink-3)">Select an agent to start chatting</p>
      </div>
    );
  }

  return (
    <>
    <div className="flex-1 flex flex-col min-h-0 bg-(--color-background)">
      <header className="flex items-center justify-between px-8 py-4 border-b border-(--color-rule-soft)">
        <div>
          <h2 className="text-[15px] font-semibold text-(--color-foreground) tracking-[-0.01em]">{selectedAgent.name}</h2>
          <p className="text-[12px] text-(--color-ink-2) mt-0.5 flex items-center gap-1.5">
            <span className={cn(
              "w-1.5 h-1.5 rounded-full",
              agentState === "waiting" && "bg-(--color-success)",
              agentState === "running" && "bg-(--color-success) animate-halo-green-yellow",
              agentState === "error" && "bg-(--color-danger)",
              agentState === "ready" && "bg-(--color-ink-4)"
            )} />
            <span className="capitalize">{agentState}</span>
            {agentModel && <span className="text-(--color-ink-3)">· {agentModel.name}</span>}
            {selectedAgent.type === "team" && <span className="text-(--color-ink-3)">· Team</span>}
          </p>
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={toggleSessionPanel}
            className={cn(
              "flex items-center gap-1.5 px-3 h-7 text-[12.5px] font-medium rounded-l-full transition-colors",
              sessionPanelOpen
                ? "bg-(--color-primary) text-white"
                : "bg-(--color-secondary) hover:bg-(--color-border) text-(--color-foreground)"
            )}
          >
            <span className="font-mono text-[11.5px]">
              {currentSessionId ? currentSessionId.substring(0, 19) : "No session"}
            </span>
          </button>
          <button
            onClick={() => { if (selectedAgent && !sessionActionsDisabled) createNewSession(selectedAgent.id); }}
            disabled={sessionActionsDisabled}
            className={cn(
              "flex items-center justify-center w-7 h-7 text-[12.5px] font-medium rounded-r-full transition-colors border-l",
              sessionPanelOpen
                ? "bg-(--color-primary) text-white border-white/20"
                : "bg-(--color-secondary) hover:bg-(--color-border) text-(--color-foreground) border-(--color-border)",
              "disabled:opacity-45 disabled:cursor-not-allowed disabled:hover:bg-(--color-secondary)"
            )}
            title={sessionActionsDisabled ? "Cannot create a new session while agent is running" : "New session"}
          >
            <Plus size={13} />
          </button>
        </div>
      </header>
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto overflow-x-hidden">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-(--color-ink-3)">
              <div className="w-12 h-12 rounded-full bg-(--color-secondary) flex items-center justify-center mb-3">
                <Sparkles size={18} className="text-(--color-ink-2)" />
              </div>
              <p className="text-[14px] font-medium text-(--color-ink-2)">Start a conversation</p>
              <p className="text-[12px] mt-1 text-(--color-ink-3)">Send a message to begin</p>
            </div>
          ) : (
            <div className="w-full max-w-[880px] mx-auto px-4">
              <div className="flex">
                <div className="flex-1 min-w-0">
                  {hiddenSegmentCount > 0 && (
                    <div className="py-3 flex justify-center border-b border-(--color-rule-soft)">
                      <button
                        onClick={() =>
                          setVisibleSegmentState({
                            scope: visibleSegmentScope,
                            count: visibleSegmentCount + SEGMENT_PAGE_SIZE,
                          })
                        }
                        className="h-8 px-3 rounded-md bg-(--color-secondary) hover:bg-(--color-secondary-hover) text-[12.5px] font-medium text-(--color-foreground) transition-colors"
                      >
                        Load {Math.min(SEGMENT_PAGE_SIZE, hiddenSegmentCount)} earlier turns
                      </button>
                    </div>
                  )}
                  {visibleSegments.map((seg) => {
                    if (seg.length === 1 && isStandalone(seg[0])) {
                      return <TurnBlock key={seg[0].id} message={seg[0]} />;
                    }
                    return (
                      <TurnGroup
                        key={`group-${seg[0].id}`}
                        messages={seg}
                        isRunning={isRunning}
                        streamingMsgId={streamingMsgId}
                        collapsedSections={collapsedSections}
                        onToggleSection={toggleSection}
                      />
                    );
                  })}
                </div>
                {turns.length >= 2 && (
                  <TurnDots turns={turns} scrollContainerRef={scrollContainerRef} />
                )}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      {timerPanelOpen && selectedAgent && (
        <TimerPanel agentId={selectedAgent.id} />
      )}
      <div className="py-4 border-t border-(--color-rule-soft) bg-(--color-background)">
        <div className="w-full max-w-[880px] mx-auto px-4">
          {/* Context usage + Timer row */}
          <div className="flex items-center gap-2 mb-2">
            {/* Circular context usage indicator */}
            {(() => {
              const maxTokens = agentModel?.maxContextTokens || 0;
              if (maxTokens <= 0) return null;
              const ratio = Math.min(contextTokens / maxTokens, 1);
              const pct = Math.round(ratio * 100);
              const size = 20;
              const radius = 7;
              const circumference = 2 * Math.PI * radius;
              const strokeColor = ratio >= 0.9
                ? "#ef4444"
                : ratio >= 0.7
                  ? "#f59e0b"
                  : "var(--color-primary)";
              return (
                <div className="relative group flex items-center justify-center h-7 w-7 rounded-md border border-(--color-border) bg-(--color-tint)" title={`${contextTokens.toLocaleString()} / ${maxTokens.toLocaleString()} tokens`}>
                  <svg width={size} height={size} className="-rotate-90">
                    <circle
                      cx={size / 2}
                      cy={size / 2}
                      r={radius}
                      fill="none"
                      stroke="var(--color-secondary)"
                      strokeWidth="2"
                    />
                    <circle
                      cx={size / 2}
                      cy={size / 2}
                      r={radius}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeDasharray={circumference}
                      strokeDashoffset={circumference * (1 - ratio)}
                      className="transition-all duration-300"
                    />
                  </svg>
                  <span className={cn(
                    "absolute text-[7.5px] font-semibold tabular-nums",
                    ratio >= 0.9 ? "text-red-500" : "text-(--color-ink-2)"
                  )}>
                    {pct}%
                  </span>
                  {/* Hover tooltip */}
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 bg-(--color-foreground) text-white text-[10.5px] rounded-md whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                    {contextTokens.toLocaleString()} / {maxTokens.toLocaleString()}
                  </div>
                </div>
              );
            })()}
            <button
              onClick={() => setTimerPanelOpen((v) => !v)}
              className={cn(
                "flex items-center gap-1.5 px-2.5 h-7 text-[12px] rounded-md border border-(--color-border) bg-(--color-tint) transition-colors",
                timerPanelOpen
                  ? "bg-(--color-primary)/10 text-(--color-primary) border-(--color-primary)/20"
                  : "text-(--color-ink-2) hover:bg-(--color-secondary)"
              )}
              title="Timers"
            >
              <Timer size={13} />
              <span className="font-medium">Timer</span>
              {agentTimers.length > 0 && (
                <span className="font-medium tabular-nums text-[10.5px] bg-(--color-secondary) px-1.5 py-0.5 rounded-full">
                  {agentTimers.length}
                </span>
              )}
            </button>
          </div>
          {attachments.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 mb-2">
              {attachments.map((attachment) => (
                <span
                  key={attachment.id}
                  title={attachment.path}
                  className="inline-flex items-center gap-1.5 max-w-full h-7 px-2 rounded-md border border-(--color-border) bg-(--color-tint) text-[11.5px] text-(--color-foreground)"
                >
                  <FileText size={12} className="shrink-0 text-(--color-ink-2)" />
                  <span className="truncate max-w-[220px]">{attachment.originalName}</span>
                  <span className="shrink-0 text-(--color-ink-3)">{formatAttachmentSize(attachment.size)}</span>
                  <button
                    onClick={() => removeAttachment(attachment.id)}
                    className="shrink-0 text-(--color-ink-3) hover:text-(--color-foreground)"
                    title="Remove file"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="flex items-center gap-2 bg-(--color-tint) border border-(--color-border) rounded-xl p-2 transition-all focus-within:bg-white focus-within:border-(--color-primary) focus-within:shadow-[0_0_0_3px_rgba(0,102,204,0.12)]">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(event) => {
                const files = event.currentTarget.files;
                if (files) void handleFileUpload(files);
                event.currentTarget.value = "";
              }}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploadingAttachments || agentState !== "waiting"}
              className="w-7 h-7 rounded-full flex items-center justify-center self-center shrink-0 text-(--color-ink-2) hover:bg-(--color-secondary) disabled:opacity-30 disabled:cursor-not-allowed"
              title={isUploadingAttachments ? "Uploading files" : "Attach files"}
            >
              <Paperclip size={14} />
            </button>
            <textarea value={input} onChange={(e) => {
              if (selectedAgent) setAgentInput(selectedAgent.id, e.target.value);
              const el = e.target;
              el.style.height = "auto";
              el.style.height = Math.min(el.scrollHeight, 120) + "px";
            }} onKeyDown={handleKeyDown}
              onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; }}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files.length > 0) {
                  void handleFileUpload(e.dataTransfer.files);
                  return;
                }
                const path = e.dataTransfer.getData("text/plain");
                if (path && selectedAgent) {
                  setAgentInput(selectedAgent.id, input ? `${input} ${path}` : path);
                }
              }}
              placeholder={attachments.length > 0 ? "Add a note…" : "Message…"} rows={1}
              className="flex-1 bg-transparent border-0 outline-none resize-none text-[14.5px] leading-[1.5] text-(--color-foreground) placeholder:text-(--color-ink-3) px-2 py-1.5"
              style={{ minHeight: "32px", maxHeight: "120px" }} />
            {isRunning ? (
              <button onClick={handleInterrupt}
                className="w-7 h-7 rounded-full flex items-center justify-center self-center shrink-0 bg-(--color-danger) text-white transition-colors hover:opacity-90"
                title="Stop">
                <Square size={11} fill="currentColor" />
              </button>
            ) : (
              <button onClick={handleSend} disabled={!canSend}
                className={cn("w-7 h-7 rounded-full flex items-center justify-center self-center shrink-0 transition-colors", "bg-(--color-foreground) text-white", "hover:bg-black disabled:opacity-30 disabled:cursor-not-allowed")}
                title="Send">
                <ArrowUp size={14} strokeWidth={2.5} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
    </>
  );
}
