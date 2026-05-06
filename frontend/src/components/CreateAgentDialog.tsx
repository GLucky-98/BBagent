import { useState } from "react";
import { X, Bot, Users, Plus, Trash2 } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import type { Agent } from "../types";

interface SingleAgentForm {
  name: string;
  basePath: string;
  primaryModelId: string;
  secondaryModelId: string;
  systemPrompt: string;
  contextHook: string;
}

interface TeamForm {
  name: string;
  teamPrompt: string;
  memberIds: string[];
  visibleMembers: Record<string, string[]>;
}

function TypeSelection({
  onSelect,
}: {
  onSelect: (type: "single" | "team") => void;
}) {
  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-1">Create New Agent</h2>
      <p className="text-sm text-[--color-muted-foreground] mb-6">
        Choose the type of agent to create
      </p>

      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={() => onSelect("single")}
          className={cn(
            "p-6 rounded-xl border-2 border-[--color-border] transition-all duration-200",
            "hover:border-[--color-primary] hover:bg-[--color-primary]/5",
            "flex flex-col items-center gap-3"
          )}
        >
          <div className="w-12 h-12 rounded-full bg-[--color-primary]/10 flex items-center justify-center">
            <Bot size={24} className="text-[--color-primary]" />
          </div>
          <div className="text-center">
            <p className="font-medium">Single Agent</p>
            <p className="text-xs text-[--color-muted-foreground] mt-1">
              Create a standalone agent
            </p>
          </div>
        </button>

        <button
          onClick={() => onSelect("team")}
          className={cn(
            "p-6 rounded-xl border-2 border-[--color-border] transition-all duration-200",
            "hover:border-[--color-primary] hover:bg-[--color-primary]/5",
            "flex flex-col items-center gap-3"
          )}
        >
          <div className="w-12 h-12 rounded-full bg-[--color-primary]/10 flex items-center justify-center">
            <Users size={24} className="text-[--color-primary]" />
          </div>
          <div className="text-center">
            <p className="font-medium">Agent Team</p>
            <p className="text-xs text-[--color-muted-foreground] mt-1">
              Create a team of agents
            </p>
          </div>
        </button>
      </div>
    </div>
  );
}

function SingleAgentFormComponent({
  onNext,
}: {
  onNext: (form: SingleAgentForm) => void;
}) {
  const models = useAppStore((s) => s.models);
  const [form, setForm] = useState<SingleAgentForm>({
    name: "",
    basePath: "",
    primaryModelId: models[0]?.id || "",
    secondaryModelId: "",
    systemPrompt: "",
    contextHook: "",
  });

  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-1">Configure Single Agent</h2>
      <p className="text-sm text-[--color-muted-foreground] mb-6">
        Fill in the agent configuration details
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1.5">Name</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="My Agent"
            className={cn(
              "w-full px-3 py-2 rounded-lg border border-[--color-border]",
              "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]"
            )}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">Base Path</label>
          <input
            type="text"
            value={form.basePath}
            onChange={(e) => setForm({ ...form, basePath: e.target.value })}
            placeholder="/path/to/agent"
            className={cn(
              "w-full px-3 py-2 rounded-lg border border-[--color-border]",
              "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]"
            )}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1.5">
              Primary Model
            </label>
            <select
              value={form.primaryModelId}
              onChange={(e) =>
                setForm({ ...form, primaryModelId: e.target.value })
              }
              className={cn(
                "w-full px-3 py-2 rounded-lg border border-[--color-border]",
                "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]"
              )}
            >
              <option value="">Select model</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">
              Secondary Model
            </label>
            <select
              value={form.secondaryModelId}
              onChange={(e) =>
                setForm({ ...form, secondaryModelId: e.target.value })
              }
              className={cn(
                "w-full px-3 py-2 rounded-lg border border-[--color-border]",
                "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]"
              )}
            >
              <option value="">Optional</option>
              {models.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">
            System Prompt
          </label>
          <textarea
            value={form.systemPrompt}
            onChange={(e) =>
              setForm({ ...form, systemPrompt: e.target.value })
            }
            placeholder="You are a helpful assistant..."
            rows={4}
            className={cn(
              "w-full px-3 py-2 rounded-lg border border-[--color-border]",
              "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]",
              "resize-none"
            )}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">
            Context Hook
          </label>
          <input
            type="text"
            value={form.contextHook}
            onChange={(e) => setForm({ ...form, contextHook: e.target.value })}
            placeholder="Optional hook function path"
            className={cn(
              "w-full px-3 py-2 rounded-lg border border-[--color-border]",
              "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]"
            )}
          />
        </div>

        <button
          onClick={() => onNext(form)}
          className={cn(
            "w-full py-2.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground]",
            "hover:opacity-90 transition-opacity font-medium"
          )}
        >
          Continue
        </button>
      </div>
    </div>
  );
}

function TeamConfigComponent({
  onBack,
  onComplete,
}: {
  onBack: () => void;
  onComplete: (form: TeamForm) => void;
}) {
  const [form, setForm] = useState<TeamForm>({
    name: "",
    teamPrompt: "",
    memberIds: [],
    visibleMembers: {},
  });

  const [tempAgents, setTempAgents] = useState<Agent[]>([]);
  const [step, setStep] = useState<"members" | "config">("members");

  const addTempAgent = () => {
    const newAgent: Agent = {
      id: crypto.randomUUID(),
      name: `Agent ${tempAgents.length + 1}`,
      type: "single",
      basePath: "",
      primaryModel: {
        id: "",
        name: "claude-sonnet-4-20250514",
        type: "chat",
        provider: "anthropic",
        baseUrl: "https://api.anthropic.com",
        apiKey: "",
        modelName: "claude-sonnet-4-20250514",
      },
      systemPrompt: "",
      tools: [],
      skills: [],
      messages: [],
    };
    setTempAgents([...tempAgents, newAgent]);
  };

  const removeTempAgent = (id: string) => {
    setTempAgents(tempAgents.filter((a) => a.id !== id));
  };

  const updateTempAgent = (id: string, updates: Partial<Agent>) => {
    setTempAgents(
      tempAgents.map((a) => (a.id === id ? { ...a, ...updates } : a))
    );
  };

  const handleComplete = () => {
    onComplete(form);
  };

  if (step === "members") {
    return (
      <div className="p-6">
        <h2 className="text-lg font-semibold mb-1">Configure Team Members</h2>
        <p className="text-sm text-[--color-muted-foreground] mb-6">
          Add and configure individual agents for your team
        </p>

        <div className="space-y-3 max-h-[400px] overflow-y-auto mb-4">
          {tempAgents.map((agent, idx) => (
            <div
              key={agent.id}
              className="p-4 rounded-lg border border-[--color-border] bg-[--color-secondary]/30"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="font-medium text-sm">Agent {idx + 1}</span>
                <button
                  onClick={() => removeTempAgent(agent.id)}
                  className="text-[--color-danger] hover:opacity-70"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <input
                type="text"
                value={agent.name}
                onChange={(e) => updateTempAgent(agent.id, { name: e.target.value })}
                placeholder="Agent name"
                className={cn(
                  "w-full px-3 py-2 rounded-lg border border-[--color-border] mb-2",
                  "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring] text-sm"
                )}
              />
              <input
                type="text"
                value={agent.systemPrompt}
                onChange={(e) =>
                  updateTempAgent(agent.id, { systemPrompt: e.target.value })
                }
                placeholder="System prompt"
                className={cn(
                  "w-full px-3 py-2 rounded-lg border border-[--color-border]",
                  "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring] text-sm"
                )}
              />
            </div>
          ))}
        </div>

        <button
          onClick={addTempAgent}
          className={cn(
            "w-full py-2.5 rounded-lg border-2 border-dashed border-[--color-border]",
            "hover:border-[--color-primary] hover:bg-[--color-primary]/5 transition-all",
            "flex items-center justify-center gap-2 text-sm text-[--color-muted-foreground]"
          )}
        >
          <Plus size={16} />
          Add Agent
        </button>

        {tempAgents.length > 0 && (
          <button
            onClick={() => setStep("config")}
            className={cn(
              "w-full py-2.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground]",
              "hover:opacity-90 transition-opacity font-medium mt-4"
            )}
          >
            Next: Configure Team
          </button>
        )}

        <button
          onClick={onBack}
          className={cn(
            "w-full py-2.5 rounded-lg border border-[--color-border] mt-2",
            "hover:bg-[--color-secondary] transition-all text-sm"
          )}
        >
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-1">Configure Team</h2>
      <p className="text-sm text-[--color-muted-foreground] mb-6">
        Set up the team name and coordination prompt
      </p>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1.5">Team Name</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="My Agent Team"
            className={cn(
              "w-full px-3 py-2 rounded-lg border border-[--color-border]",
              "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]"
            )}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">
            Team Members
          </label>
          <div className="space-y-2">
            {tempAgents.map((agent) => (
              <div
                key={agent.id}
                className="flex items-center gap-2 p-2 rounded-lg bg-[--color-secondary]/30"
              >
                <input
                  type="checkbox"
                  checked={form.memberIds.includes(agent.id)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setForm({
                        ...form,
                        memberIds: [...form.memberIds, agent.id],
                      });
                    } else {
                      setForm({
                        ...form,
                        memberIds: form.memberIds.filter((id) => id !== agent.id),
                      });
                    }
                  }}
                  className="rounded"
                />
                <span className="text-sm">{agent.name}</span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">
            Team Coordination Prompt
          </label>
          <textarea
            value={form.teamPrompt}
            onChange={(e) => setForm({ ...form, teamPrompt: e.target.value })}
            placeholder="Instructions for how agents should collaborate..."
            rows={4}
            className={cn(
              "w-full px-3 py-2 rounded-lg border border-[--color-border]",
              "bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]",
              "resize-none"
            )}
          />
        </div>

        <button
          onClick={handleComplete}
          disabled={!form.name || tempAgents.length === 0}
          className={cn(
            "w-full py-2.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground]",
            "hover:opacity-90 transition-opacity font-medium",
            "disabled:opacity-50 disabled:cursor-not-allowed"
          )}
        >
          Complete
        </button>

        <button
          onClick={() => setStep("members")}
          className={cn(
            "w-full py-2.5 rounded-lg border border-[--color-border]",
            "hover:bg-[--color-secondary] transition-all text-sm"
          )}
        >
          Back
        </button>
      </div>
    </div>
  );
}

export function CreateAgentDialog() {
  const isOpen = useAppStore((s) => s.isCreateDialogOpen);
  const createType = useAppStore((s) => s.createType);
  const setIsOpen = useAppStore((s) => s.setIsCreateDialogOpen);
  const setCreateType = useAppStore((s) => s.setCreateType);
  const addAgent = useAppStore((s) => s.addAgent);
  const addTeam = useAppStore((s) => s.addTeam);
  const models = useAppStore((s) => s.models);

  const handleClose = () => {
    setIsOpen(false);
    setCreateType(null);
  };

  const handleTypeSelect = (type: "single" | "team") => {
    setCreateType(type);
  };

  const handleSingleAgentComplete = (form: SingleAgentForm) => {
    const primaryModel = models.find((m) => m.id === form.primaryModelId);
    const secondaryModel = models.find((m) => m.id === form.secondaryModelId);

    const agent: Agent = {
      id: crypto.randomUUID(),
      name: form.name,
      type: "single",
      basePath: form.basePath,
      primaryModel: primaryModel || {
        id: "",
        name: "claude-sonnet-4-20250514",
        type: "chat",
        provider: "anthropic",
        baseUrl: "https://api.anthropic.com",
        apiKey: "",
        modelName: "claude-sonnet-4-20250514",
      },
      secondaryModel: secondaryModel,
      systemPrompt: form.systemPrompt,
      tools: [],
      skills: [],
      contextHook: form.contextHook,
      messages: [],
    };

    addAgent(agent);
    handleClose();
  };

  const handleTeamComplete = (form: TeamForm) => {
    const team: Agent = {
      id: crypto.randomUUID(),
      name: form.name,
      type: "team",
      basePath: "",
      primaryModel: {
        id: "",
        name: "claude-sonnet-4-20250514",
        type: "chat",
        provider: "anthropic",
        baseUrl: "https://api.anthropic.com",
        apiKey: "",
        modelName: "claude-sonnet-4-20250514",
      },
      systemPrompt: form.teamPrompt,
      tools: [],
      skills: [],
      teamPrompt: form.teamPrompt,
      messages: [],
    };

    addTeam(team);
    handleClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/20 backdrop-blur-sm"
        onClick={handleClose}
      />

      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-[--color-secondary] transition-colors"
        >
          <X size={18} />
        </button>

        {!createType && <TypeSelection onSelect={handleTypeSelect} />}
        {createType === "single" && (
          <SingleAgentFormComponent onNext={handleSingleAgentComplete} />
        )}
        {createType === "team" && (
          <TeamConfigComponent
            onBack={() => setCreateType(null)}
            onComplete={handleTeamComplete}
          />
        )}
      </div>
    </div>
  );
}
