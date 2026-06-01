import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { Message } from "../types";

const AGENT_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
];

function TeamMessageBubble({ message, color }: { message: Message; color: string }) {
  const isUser = message.role === "user";
  const isSystem = message.role === "system";

  if (isSystem) {
    return (
      <div className="flex justify-center mb-4">
        <span className="text-xs text-(--color-muted-foreground) bg-(--color-muted) px-3 py-1 rounded-full">
          {message.content}
        </span>
      </div>
    );
  }

  return (
    <div className="flex gap-3 mb-4">
      <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0" style={{ backgroundColor: isUser ? "var(--color-primary)" : color }}>
        {isUser ? <User size={14} className="text-white" /> : <Bot size={14} className="text-white" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span className="text-xs font-medium" style={{ color }}>
            {message.sourceAgent || (isUser ? "You" : "Agent")}
          </span>
          <span className="text-[10px] text-(--color-muted-foreground)">
            {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
        </div>
        <div className="rounded-2xl rounded-tl-sm px-4 py-2.5 bg-(--color-secondary) inline-block max-w-[85%]">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        </div>
      </div>
    </div>
  );
}

export function TeamChatWindow() {
  const agents = useAppStore((s) => s.agents);
  const activeAgentName = useAppStore((s) => s.activeAgentName);
  const addMessage = useAppStore((s) => s.addMessage);

  const team = agents.find((a) => a.name === activeAgentName && a.type === "team");
  const members = team?.teamMembers || [];

  const [input, setInput] = useState("");
  const [mentionFilter, setMentionFilter] = useState("");
  const [showMentionDropdown, setShowMentionDropdown] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const agentColorMapRef = useRef<Record<string, string>>({});
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const getAgentColor = (name: string) => {
    if (!agentColorMapRef.current[name]) {
      const idx = Object.keys(agentColorMapRef.current).length % AGENT_COLORS.length;
      agentColorMapRef.current[name] = AGENT_COLORS[idx];
    }
    return agentColorMapRef.current[name];
  };

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => { scrollToBottom(); }, [team?.messages]);

  const connectWs = useCallback((teamName: string) => {
    if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
      wsRef.current.close();
    }
    const wsBase = (import.meta.env.VITE_API_BASE || "http://localhost:8000/api").replace(/^http/, "ws");
    const ws = new WebSocket(`${wsBase}/ws/team/${teamName}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const chunk = JSON.parse(event.data);
        if (!teamName) return;

        if (chunk.type === "text" && chunk.content) {
          addMessage(teamName, {
            id: crypto.randomUUID(),
            role: "assistant",
            content: chunk.content,
            timestamp: Date.now(),
            sourceAgent: chunk.source_agent,
            messageId: chunk.message_id,
          });
        } else if (chunk.type === "thinking" && chunk.content) {
          addMessage(teamName, {
            id: crypto.randomUUID(),
            role: "system",
            content: `[${chunk.source_agent || "agent"} thinking] ${chunk.content}`,
            timestamp: Date.now(),
            sourceAgent: chunk.source_agent,
          });
        } else if (chunk.type === "system") {
          addMessage(teamName, {
            id: crypto.randomUUID(),
            role: "system",
            content: chunk.content,
            timestamp: Date.now(),
          });
        } else if (chunk.type === "error") {
          addMessage(teamName, {
            id: crypto.randomUUID(),
            role: "system",
            content: `Error from ${chunk.source_agent || "agent"}: ${chunk.content}`,
            timestamp: Date.now(),
            sourceAgent: chunk.source_agent,
          });
        }
      } catch {
        // ignore parse errors
      }
    };
  }, [addMessage]);

  useEffect(() => {
    if (team) {
      connectWs(team.name);
    }
    return () => {
      wsRef.current?.close();
    };
  }, [team?.name, connectWs]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setInput(val);

    const atMatch = val.match(/@(\S*)$/);
    if (atMatch) {
      setMentionFilter(atMatch[1].toLowerCase());
      setShowMentionDropdown(true);
    } else {
      setShowMentionDropdown(false);
    }
  };

  const handleMentionSelect = (memberName: string) => {
    const newInput = input.replace(/@\S*$/, `@${memberName} `);
    setInput(newInput);
    setShowMentionDropdown(false);
    inputRef.current?.focus();
  };

  const handleSend = () => {
    if (!input.trim() || !team) return;

    const mentions: string[] = [];
    let mentionMatch;
    const mentionRegex = /@([a-zA-Z0-9_]+)/g;
    while ((mentionMatch = mentionRegex.exec(input)) !== null) {
      mentions.push(mentionMatch[1]);
    }

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: input.trim(),
      timestamp: Date.now(),
    };
    addMessage(team.name, userMsg);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "user_message",
        content: input.trim(),
        mentions: mentions.length > 0 ? mentions : undefined,
      }));
    }
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!team) {
    return (
      <div className="flex-1 flex items-center justify-center bg-(--color-background) text-(--color-muted-foreground)">
        <p>No team selected</p>
      </div>
    );
  }

  const filteredMembers = showMentionDropdown
    ? members.filter((m) => m.name.toLowerCase().includes(mentionFilter))
    : [];

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-(--color-background)">
      <header className="px-6 py-4 bg-white border-b border-(--color-border)">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-(--color-primary)/10 flex items-center justify-center">
            <Bot size={20} className="text-(--color-primary)" />
          </div>
          <div>
            <h2 className="font-semibold text-(--color-foreground)">{team.name} - Team Chat</h2>
            <p className="text-xs text-(--color-muted-foreground)">
              {members.length} members: {members.map((m) => m.name).join(", ")}
            </p>
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {team.messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-(--color-muted-foreground)">
            <div className="w-16 h-16 rounded-full bg-(--color-secondary) flex items-center justify-center mb-4"><Bot size={28} /></div>
            <p className="text-sm">Team chat is ready</p>
            <p className="text-xs mt-1">Use @agent_name to send messages to team members</p>
          </div>
        ) : (
          team.messages.map((msg) => (
            <TeamMessageBubble
              key={msg.id}
              message={msg}
              color={msg.sourceAgent ? getAgentColor(msg.sourceAgent) : "var(--color-primary)"}
            />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className="p-4 bg-white border-t border-(--color-border) relative">
        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder="Type @agent_name to message a team member..."
              rows={1}
              className={cn("w-full px-4 py-3 rounded-xl border border-(--color-border)", "bg-(--color-background) resize-none", "focus:outline-none focus:ring-2 focus:ring-(--color-ring) focus:border-transparent", "placeholder:text-(--color-muted-foreground)")}
              style={{ minHeight: "48px", maxHeight: "120px" }}
            />
            {showMentionDropdown && filteredMembers.length > 0 && (
              <div className="absolute bottom-full left-0 mb-1 w-52 bg-white rounded-lg shadow-lg border border-(--color-border) max-h-40 overflow-y-auto z-50">
                {filteredMembers.map((m) => (
                  <button
                    key={m.name}
                    onClick={() => handleMentionSelect(m.name)}
                    className="w-full text-left px-3 py-2 text-sm hover:bg-(--color-secondary) flex items-center gap-2"
                  >
                    <div className="w-5 h-5 rounded-full flex items-center justify-center" style={{ backgroundColor: getAgentColor(m.name) }}>
                      <Bot size={10} className="text-white" />
                    </div>
                    {m.name}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button onClick={handleSend} disabled={!input.trim()}
            className={cn("w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border border-(--color-border)", "bg-(--color-primary) text-(--color-primary-foreground)", "transition-all duration-200", "hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed")}>
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
