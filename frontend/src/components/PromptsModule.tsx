import { FileText, Copy, Check } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import { useState } from "react";

function PromptList() {
  const prompts = useAppStore((s) => s.prompts);
  const selectedPromptId = useAppStore((s) => s.selectedPromptId);
  const setSelectedPromptId = useAppStore((s) => s.setSelectedPromptId);

  return (
    <div className="w-[320px] h-screen bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-3 border-b border-[--color-border]">
        <div className="h-10 flex items-center px-3">
          <span className="text-sm font-medium text-[--color-muted-foreground]">
            {prompts.length} built-in prompts
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {prompts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <FileText size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No prompts available</p>
          </div>
        ) : (
          <div className="space-y-1">
            {prompts.map((prompt) => (
              <button
                key={prompt.id}
                onClick={() => setSelectedPromptId(prompt.id)}
                className={cn(
                  "w-full flex items-start gap-3 px-3 py-3 rounded-lg text-left transition-all duration-150",
                  "hover:bg-[--color-secondary]",
                  selectedPromptId === prompt.id && "bg-[--color-primary]/10 text-[--color-primary]"
                )}
              >
                <div className="w-8 h-8 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center shrink-0">
                  <FileText size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{prompt.name}</p>
                  <p className="text-xs text-[--color-muted-foreground] mt-0.5 line-clamp-2">
                    {prompt.description}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PromptDetailPanel() {
  const prompts = useAppStore((s) => s.prompts);
  const selectedPromptId = useAppStore((s) => s.selectedPromptId);
  const [copied, setCopied] = useState(false);

  const selectedPrompt = prompts.find((p) => p.id === selectedPromptId);

  const handleCopy = () => {
    if (selectedPrompt) {
      navigator.clipboard.writeText(selectedPrompt.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!selectedPrompt) {
    return (
      <div className="flex-1 h-screen flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
        <FileText size={48} className="mb-4 opacity-30" />
        <p className="text-lg font-medium">No prompt selected</p>
        <p className="text-sm mt-1">Select a prompt to view details</p>
      </div>
    );
  }

  return (
    <div className="flex-1 h-screen flex flex-col bg-[--color-background]">
      <header className="px-6 py-4 bg-white border-b border-[--color-border]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center">
              <FileText size={20} />
            </div>
            <div>
              <h2 className="font-semibold text-[--color-foreground]">
                {selectedPrompt.name}
              </h2>
              <p className="text-xs text-[--color-muted-foreground]">
                Built-in Prompt
              </p>
            </div>
          </div>

          <button
            onClick={handleCopy}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-all",
              copied
                ? "bg-emerald-100 text-emerald-600"
                : "bg-[--color-secondary] text-[--color-foreground] hover:bg-[--color-secondary]/80"
            )}
          >
            {copied ? <Check size={16} /> : <Copy size={16} />}
            <span>{copied ? "Copied!" : "Copy"}</span>
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          <div>
            <h3 className="text-sm font-medium mb-2">Description</h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <p className="text-sm text-[--color-foreground]">
                {selectedPrompt.description}
              </p>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2">Prompt Content</h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <pre className="text-sm whitespace-pre-wrap text-[--color-foreground] leading-relaxed font-mono">
                {selectedPrompt.content}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function PromptsModule() {
  return (
    <>
      <PromptList />
      <PromptDetailPanel />
    </>
  );
}
