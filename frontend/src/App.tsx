import { useEffect } from "react";
import { TopNav } from "./components/layout/TopNav";
import { OnboardingView } from "./components/onboarding/OnboardingView";
import { WorkspaceView } from "./components/workspace/WorkspaceView";
import { AgentConfigDialog } from "./components/agents/AgentConfigDialog";
import { ToastContainer } from "./components/ToastContainer";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useAppStore } from "./store";

function App() {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const configDialog = useAppStore((s) => s.configDialog);
  const closeConfigDialog = useAppStore((s) => s.closeConfigDialog);
  const loadAll = useAppStore((s) => s.loadAll);
  const isOnboarding = !activeAgentId;

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
          agentId={configDialog.agentId}
        />
        <ToastContainer />
      </div>
    </ErrorBoundary>
  );
}

export default App;
