import { useState, useRef, useEffect } from "react";
import { Send, Bot, User } from "lucide-react";
import { useAppStore, useSelectedAgent, useAgentModel } from "../store";
import { cn } from "../lib/utils";
import type { Message } from "../types";

function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
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
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => { scrollToBottom(); }, [selectedAgent?.messages]);

  const handleSend = () => {
    if (!input.trim() || !selectedAgent) return;
    const userMessage: Message = { id: crypto.randomUUID(), role: "user", content: input.trim(), timestamp: Date.now() };
    addMessage(selectedAgent.id, userMessage);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

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
          <div>
            <h2 className="font-semibold text-[--color-foreground]">{selectedAgent.name}</h2>
            <p className="text-xs text-[--color-muted-foreground]">
              {selectedAgent.type === "team" ? "Agent Team" : "Single Agent"}{agentModel ? ` \u2022 ${agentModel.name}` : ""}
            </p>
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {selectedAgent.messages.length === 0 ? (
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
      <div className="p-4 bg-white border-t border-[--color-border]">
        <div className="flex items-end gap-3">
          <div className="flex-1 relative">
            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Type a message..." rows={1}
              className={cn("w-full px-4 py-3 rounded-xl border border-[--color-border]", "bg-[--color-background] resize-none", "focus:outline-none focus:ring-2 focus:ring-[--color-ring] focus:border-transparent", "placeholder:text-[--color-muted-foreground]")}
              style={{ minHeight: "48px", maxHeight: "120px" }} />
          </div>
          <button onClick={handleSend} disabled={!input.trim()}
            className={cn("w-10 h-10 rounded-xl flex items-center justify-center shrink-0", "bg-[--color-primary] text-[--color-primary-foreground]", "transition-all duration-200", "hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed")}>
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
