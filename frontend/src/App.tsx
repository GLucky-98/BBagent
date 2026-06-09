import { useEffect } from "react";
import { TopNav } from "./components/layout/TopNav";
import { OnboardingView } from "./components/onboarding/OnboardingView";
import { WorkspaceView } from "./components/workspace/WorkspaceView";
import { AgentConfigDialog } from "./components/agents/AgentConfigDialog";
import { SettingsPopover } from "./components/settings/SettingsPopover";
import { ToastContainer } from "./components/ToastContainer";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useAppStore } from "./store";
import { useGlobalAgentState } from "./hooks/useGlobalAgentState";
import type { SettingsTab } from "./types";

function App() {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const configDialog = useAppStore((s) => s.configDialog);
  const closeConfigDialog = useAppStore((s) => s.closeConfigDialog);
  const loadAll = useAppStore((s) => s.loadAll);
  const isOnboarding = !activeAgentId;
  const isSettingsOpen = useAppStore((s) => s.isSettingsOpen);
  const closeSettings = useAppStore((s) => s.closeSettings);
  const settingsActiveTab = useAppStore((s) => s.settingsActiveTab);

  // 全局 agent_state 监听：必须在 App 级别始终存活，确保
  // 未选中 tab 时的 start/stop 操作也能更新指示灯和按钮状态。
  useGlobalAgentState();

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-screen w-screen overflow-hidden min-w-[920px] min-h-[600px]">
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

      {isSettingsOpen && (
        <SettingsPopover
          activeTab={settingsActiveTab}
          onTabChange={(tab: SettingsTab) => useAppStore.setState({ settingsActiveTab: tab })}
          onClose={closeSettings}
        />
      )}
    </ErrorBoundary>
  );
}

export default App;
