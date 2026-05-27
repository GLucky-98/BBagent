import { Bot } from "lucide-react";
import { useAppStore } from "../../store";
import { ChatWindow } from "../ChatWindow";
import { PanelA_FilePanel } from "./PanelA_FilePanel";
import { PanelC_FilePreview } from "./PanelC_FilePreview";

export function WorkspaceView() {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const previewFile = useAppStore((s) => s.previewFile);

  if (!activeAgentId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[--color-muted]/30">
        <div className="text-center">
          <Bot className="w-16 h-16 text-[--color-muted-foreground]/30 mx-auto mb-4" />
          <p className="text-lg font-medium text-[--color-muted-foreground]">
            Select an agent to start chatting
          </p>
          <p className="text-sm text-[--color-muted-foreground]/60 mt-1">
            Choose an agent from the tabs above, or create a new one
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden">
      <PanelA_FilePanel />
      <div className="flex-1 flex flex-col overflow-hidden">
        <ChatWindow />
      </div>
      {previewFile && <PanelC_FilePreview />}
    </div>
  );
}
