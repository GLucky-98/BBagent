import { useState } from "react";
import { Plus, Box, Play } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";

function ModelList() {
  const models = useAppStore((s) => s.models);
  const selectedModelId = useAppStore((s) => s.selectedModelId);
  const setSelectedModelId = useAppStore((s) => s.setSelectedModelId);

  return (
    <div className="w-[320px] h-screen bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-3 border-b border-[--color-border]">
        <button
          className={cn(
            "w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg",
            "bg-[--color-primary] text-[--color-primary-foreground]",
            "hover:opacity-90 transition-opacity"
          )}
        >
          <Plus size={16} />
          <span className="text-sm font-medium">New Model</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {models.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <Box size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No models yet</p>
          </div>
        ) : (
          <div className="space-y-1">
            {models.map((model) => (
              <button
                key={model.id}
                onClick={() => setSelectedModelId(model.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-all duration-150",
                  "hover:bg-[--color-secondary]",
                  selectedModelId === model.id && "bg-[--color-primary]/10 text-[--color-primary]"
                )}
              >
                <div
                  className={cn(
                    "w-8 h-8 rounded-lg flex items-center justify-center text-xs font-medium",
                    model.type === "chat"
                      ? "bg-[--color-primary]/10 text-[--color-primary]"
                      : "bg-emerald-100 text-emerald-600"
                  )}
                >
                  {model.type === "chat" ? "CHAT" : "EMB"}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{model.name}</p>
                  <p className="text-xs text-[--color-muted-foreground] truncate">
                    {model.provider} • {model.modelName}
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

function ModelTestPanel() {
  const models = useAppStore((s) => s.models);
  const selectedModelId = useAppStore((s) => s.selectedModelId);
  const [input, setInput] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const selectedModel = models.find((m) => m.id === selectedModelId);

  if (!selectedModel) {
    return (
      <div className="flex-1 h-screen flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
        <Box size={48} className="mb-4 opacity-30" />
        <p className="text-lg font-medium">No model selected</p>
        <p className="text-sm mt-1">Select a model to test</p>
      </div>
    );
  }

  const defaultPrompt = "Hello! Please introduce yourself in a few sentences.";

  const handleTest = () => {
    setIsLoading(true);
    setResult(null);

    setTimeout(() => {
      setIsLoading(false);
      setResult(
        `[Demo Response from ${selectedModel.name}]\n\n` +
        `Model: ${selectedModel.modelName}\n` +
        `Provider: ${selectedModel.provider}\n` +
        `Type: ${selectedModel.type}\n\n` +
        `This is a simulated response. In production, this would call the actual model API with your input:\n\n"${input || defaultPrompt}"`
      );
    }, 1500);
  };

  return (
    <div className="flex-1 h-screen flex flex-col bg-[--color-background]">
      <header className="px-6 py-4 bg-white border-b border-[--color-border]">
        <div className="flex items-center gap-3">
          <div
            className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center text-xs font-bold",
              selectedModel.type === "chat"
                ? "bg-[--color-primary]/10 text-[--color-primary]"
                : "bg-emerald-100 text-emerald-600"
            )}
          >
            {selectedModel.type === "chat" ? "CHAT" : "EMB"}
          </div>
          <div>
            <h2 className="font-semibold text-[--color-foreground]">
              {selectedModel.name}
            </h2>
            <p className="text-xs text-[--color-muted-foreground]">
              {selectedModel.provider} • {selectedModel.modelName}
            </p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          <div>
            <h3 className="text-sm font-medium mb-2">Configuration</h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4 space-y-3">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-[--color-muted-foreground]">Type:</span>
                  <span className="ml-2 font-medium capitalize">{selectedModel.type}</span>
                </div>
                <div>
                  <span className="text-[--color-muted-foreground]">Provider:</span>
                  <span className="ml-2 font-medium capitalize">{selectedModel.provider}</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[--color-muted-foreground]">Base URL:</span>
                  <span className="ml-2 font-mono text-xs">{selectedModel.baseUrl}</span>
                </div>
                <div className="col-span-2">
                  <span className="text-[--color-muted-foreground]">Model Name:</span>
                  <span className="ml-2 font-mono text-xs">{selectedModel.modelName}</span>
                </div>
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2">Test Input</h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={defaultPrompt}
                rows={4}
                className={cn(
                  "w-full rounded-lg border border-[--color-border] p-3 resize-none",
                  "focus:outline-none focus:ring-2 focus:ring-[--color-ring] focus:border-transparent",
                  "placeholder:text-[--color-muted-foreground] text-sm"
                )}
              />
              <button
                onClick={handleTest}
                disabled={isLoading}
                className={cn(
                  "mt-3 flex items-center gap-2 px-4 py-2 rounded-lg",
                  "bg-[--color-primary] text-[--color-primary-foreground]",
                  "hover:opacity-90 transition-opacity",
                  "disabled:opacity-50 disabled:cursor-not-allowed"
                )}
              >
                <Play size={16} />
                <span className="text-sm font-medium">
                  {isLoading ? "Testing..." : "Run Test"}
                </span>
              </button>
            </div>
          </div>

          {result && (
            <div>
              <h3 className="text-sm font-medium mb-2">Response</h3>
              <div className="bg-white rounded-lg border border-[--color-border] p-4">
                <pre className="text-sm whitespace-pre-wrap font-mono text-[--color-foreground]">
                  {result}
                </pre>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ModelsModule() {
  return (
    <>
      <ModelList />
      <ModelTestPanel />
    </>
  );
}
