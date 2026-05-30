import { useEffect } from "react";
import { TopNav } from "./components/layout/TopNav";
import { OnboardingView } from "./components/onboarding/OnboardingView";
import { WorkspaceView } from "./components/workspace/WorkspaceView";
import { AgentConfigDialog } from "./components/agents/AgentConfigDialog";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useAppStore } from "./store";

function App() {
  const activeAgentName = useAppStore((s) => s.activeAgentName);
  const configDialog = useAppStore((s) => s.configDialog);
  const closeConfigDialog = useAppStore((s) => s.closeConfigDialog);
  const loadAll = useAppStore((s) => s.loadAll);
  const isOnboarding = !activeAgentName;

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-screen w-screen overflow-hidden min-w-[900px] min-h-[600px]">
        <TopNav />
        {isOnboarding ? <OnboardingView /> : <WorkspaceView />}
        <AgentConfigDialog
          open={configDialog.open}
          onClose={closeConfigDialog}
          mode={configDialog.mode}
          type={configDialog.type}
          agentName={configDialog.agentName}
        />
      </div>
    </ErrorBoundary>
  );
}

export default App;
