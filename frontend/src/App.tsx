import { Sidebar } from "./components/Sidebar";
import { AgentList } from "./components/AgentList";
import { ChatWindow } from "./components/ChatWindow";
import { CreateAgentDialog } from "./components/CreateAgentDialog";
import { ModelsModule } from "./components/ModelsModule";
import { ToolsModule } from "./components/ToolsModule";
import { SkillsModule } from "./components/SkillsModule";
import { MCPsModule } from "./components/MCPsModule";
import { PromptsModule } from "./components/PromptsModule";
import { useAppStore } from "./store";

function MainContent() {
  const currentNav = useAppStore((s) => s.currentNav);

  if (currentNav === "agents") {
    return (
      <>
        <AgentList />
        <ChatWindow />
      </>
    );
  }

  if (currentNav === "models") {
    return <ModelsModule />;
  }

  if (currentNav === "tools") {
    return <ToolsModule />;
  }

  if (currentNav === "skills") {
    return <SkillsModule />;
  }

  if (currentNav === "mcps") {
    return <MCPsModule />;
  }

  if (currentNav === "prompts") {
    return <PromptsModule />;
  }

  return null;
}

function App() {
  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar />
      <MainContent />
      <CreateAgentDialog />
    </div>
  );
}

export default App;
