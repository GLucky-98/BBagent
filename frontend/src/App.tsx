import { TopNav } from "./components/layout/TopNav";
import { OnboardingView } from "./components/onboarding/OnboardingView";
import { WorkspaceView } from "./components/workspace/WorkspaceView";
import { AgentConfigDialog } from "./components/agents/AgentConfigDialog";
import { useAppStore } from "./store";

function App() {
  const agents = useAppStore((s) => s.agents);
  const configDialog = useAppStore((s) => s.configDialog);
  const closeConfigDialog = useAppStore((s) => s.closeConfigDialog);
  const isOnboarding = agents.length === 0;

  return (
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
    </div>
  );
}

export default App;
