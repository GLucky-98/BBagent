import { useState, useEffect } from "react";
import { X, Bot, Users, Search, FileText } from "lucide-react";
import { useAppStore } from "../../store";
import { cn } from "../../lib/utils";
import type { Agent, MCPServer } from "../../types";

interface AgentConfigDialogProps {
  open: boolean;
  onClose: () => void;
  mode: "create" | "edit";
  type: "agent" | "team" | "";
  agentId?: string;
}

function TypeSelection({ onSelect }: { onSelect: (t: "agent" | "team") => void }) {
  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-1">Create New Agent</h2>
      <p className="text-sm text-[--color-muted-foreground] mb-6">Choose the type of agent to create</p>
      <div className="grid grid-cols-2 gap-4">
        <button onClick={() => onSelect("agent")}
          className="p-6 rounded-xl border-2 border-[--color-border] hover:border-[--color-primary] hover:bg-[--color-primary]/5 transition-all flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-[--color-primary]/10 flex items-center justify-center"><Bot size={24} className="text-[--color-primary]" /></div>
          <div className="text-center"><p className="font-medium">Single Agent</p><p className="text-xs text-[--color-muted-foreground] mt-1">Create a standalone agent</p></div>
        </button>
        <button onClick={() => onSelect("team")}
          className="p-6 rounded-xl border-2 border-[--color-border] hover:border-[--color-primary] hover:bg-[--color-primary]/5 transition-all flex flex-col items-center gap-3">
          <div className="w-12 h-12 rounded-full bg-[--color-primary]/10 flex items-center justify-center"><Users size={24} className="text-[--color-primary]" /></div>
          <div className="text-center"><p className="font-medium">Agent Team</p><p className="text-xs text-[--color-muted-foreground] mt-1">Create a team of agents</p></div>
        </button>
      </div>
    </div>
  );
}

function SingleAgentForm({
  initialData,
  onSave,
}: {
  initialData?: {
    name: string; basePath: string; modelId: string;
    systemPrompt: string; toolNames: string[]; skillNames: string[]; hookEnabled: boolean;
  };
  onSave: (data: { name: string; basePath: string; modelId: string; systemPrompt: string; toolNames: string[]; skillNames: string[]; hookEnabled: boolean }) => void;
}) {
  const models = useAppStore((s) => s.models);
  const tools = useAppStore((s) => s.tools);
  const skills = useAppStore((s) => s.skills);
  const prompts = useAppStore((s) => s.prompts);
  const [showPromptPicker, setShowPromptPicker] = useState(false);
  const [promptFilter, setPromptFilter] = useState("");

  const [form, setForm] = useState({
    name: initialData?.name ?? "",
    basePath: initialData?.basePath ?? "",
    modelId: initialData?.modelId ?? models[0]?.id ?? "",
    systemPrompt: initialData?.systemPrompt ?? "",
    toolNames: initialData?.toolNames ?? [],
    skillNames: initialData?.skillNames ?? [],
    hookEnabled: initialData?.hookEnabled ?? true,
  });

  const builtInTools = tools.filter((t) => !t.isMcp);
  const mcpToolsByServer = tools.filter((t) => t.isMcp).reduce<Record<string, typeof tools>>((acc, t) => {
    const key = t.mcpServerName ?? "Other";
    (acc[key] ??= []).push(t);
    return acc;
  }, {});

  const filteredPrompts = prompts.filter((p) =>
    p.name.toLowerCase().includes(promptFilter.toLowerCase()) ||
    p.description.toLowerCase().includes(promptFilter.toLowerCase())
  );

  return (
    <div className="p-6">
      <h2 className="text-lg font-semibold mb-1">{initialData ? "Edit Agent" : "Configure Agent"}</h2>
      <p className="text-sm text-[--color-muted-foreground] mb-6">{initialData ? "Update agent configuration" : "Fill in the agent configuration details"}</p>

      <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
        <div>
          <label className="block text-sm font-medium mb-1.5">Name</label>
          <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="My Agent (leave empty for auto-generated)" className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]" />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">Base Path</label>
          <input type="text" value={form.basePath} onChange={(e) => setForm({ ...form, basePath: e.target.value })}
            placeholder="/workspace/agent" className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]" />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">Model</label>
          <select value={form.modelId} onChange={(e) => setForm({ ...form, modelId: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]">
            <option value="">Select a model</option>
            {models.map((m) => <option key={m.id} value={m.id}>{m.name} ({m.provider})</option>)}
          </select>
        </div>

        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-sm font-medium">System Prompt</label>
            <button onClick={() => setShowPromptPicker(!showPromptPicker)}
              className="flex items-center gap-1 text-xs text-[--color-primary] hover:underline">
              <FileText className="w-3 h-3" />
              {showPromptPicker ? "Hide Prompt Library" : "From Prompt Library"}
            </button>
          </div>
          {showPromptPicker && (
            <div className="mb-2 border border-[--color-border] rounded-lg overflow-hidden">
              <div className="flex items-center gap-1 px-3 py-2 border-b border-[--color-border] bg-[--color-muted]/20">
                <Search className="w-3 h-3 text-[--color-muted-foreground]" />
                <input type="text" value={promptFilter} onChange={(e) => setPromptFilter(e.target.value)}
                  placeholder="Filter prompts..." className="flex-1 text-xs bg-transparent outline-none" />
              </div>
              <div className="max-h-[120px] overflow-y-auto">
                {filteredPrompts.map((p) => (
                  <button key={p.id} onClick={() => { setForm({ ...form, systemPrompt: p.content }); setShowPromptPicker(false); }}
                    className="w-full text-left px-3 py-2 hover:bg-[--color-secondary] text-sm">
                    <span className="font-medium">{p.name}</span>
                    <span className="text-xs text-[--color-muted-foreground] ml-2">{p.description}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
          <textarea value={form.systemPrompt} onChange={(e) => setForm({ ...form, systemPrompt: e.target.value })}
            placeholder="You are a helpful assistant..." rows={4}
            className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring] resize-none" />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">Tools</label>
          <div className="border border-[--color-border] rounded-lg divide-y divide-[--color-border] max-h-[200px] overflow-y-auto">
            <div className="px-3 py-2 bg-[--color-muted]/20 text-xs font-medium text-[--color-muted-foreground]">Built-in Tools</div>
            <div className="px-3 py-2 space-y-1">
              {builtInTools.map((t) => (
                <label key={t.id} className="flex items-center justify-between text-sm cursor-pointer">
                  <span className="truncate">{t.name}</span>
                  <input type="checkbox" checked={form.toolNames.includes(t.name)}
                    onChange={(e) => setForm({ ...form, toolNames: e.target.checked ? [...form.toolNames, t.name] : form.toolNames.filter((n) => n !== t.name) })}
                    className="rounded shrink-0 ml-2" />
                </label>
              ))}
            </div>
            {Object.entries(mcpToolsByServer).map(([serverName, serverTools]) => (
              <div key={serverName}>
                <div className="px-3 py-2 bg-[--color-muted]/20 text-xs font-medium text-[--color-muted-foreground]">MCP: {serverName}</div>
                <div className="px-3 py-2 space-y-1">
                  {serverTools.map((t) => (
                    <label key={t.id} className="flex items-center justify-between text-sm cursor-pointer">
                      <span className="truncate">{t.name}</span>
                      <input type="checkbox" checked={form.toolNames.includes(t.name)}
                        onChange={(e) => setForm({ ...form, toolNames: e.target.checked ? [...form.toolNames, t.name] : form.toolNames.filter((n) => n !== t.name) })}
                        className="rounded shrink-0 ml-2" />
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1.5">Skills</label>
          <div className="border border-[--color-border] rounded-lg max-h-[150px] overflow-y-auto p-3 space-y-1">
            {skills.map((s) => (
              <label key={s.name} className="flex items-center justify-between text-sm cursor-pointer">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="truncate">{s.name}</span>
                  <span className="text-xs text-[--color-muted-foreground] shrink-0">{s.metadata.version && `v${s.metadata.version}`}</span>
                </div>
                <input type="checkbox" checked={form.skillNames.includes(s.name)}
                  onChange={(e) => setForm({ ...form, skillNames: e.target.checked ? [...form.skillNames, s.name] : form.skillNames.filter((n) => n !== s.name) })}
                  className="rounded shrink-0 ml-2" />
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="flex items-center justify-between">
            <div>
              <span className="text-sm font-medium">Built-in Hook</span>
              <p className="text-xs text-[--color-muted-foreground] mt-0.5">Context compression & memory management</p>
            </div>
            <button onClick={() => setForm({ ...form, hookEnabled: !form.hookEnabled })}
              className={cn(
                "relative w-11 h-6 rounded-full transition-colors shadow-inner",
                form.hookEnabled
                  ? "bg-emerald-500"
                  : "bg-gray-300"
              )}>
              <div className={cn(
                "absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform",
                form.hookEnabled ? "translate-x-[22px]" : "translate-x-0.5"
              )} />
            </button>
          </label>
        </div>

        <button onClick={() => onSave(form)} disabled={!form.modelId}
          className="w-full py-2.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] hover:opacity-90 transition-opacity font-medium disabled:opacity-50 disabled:cursor-not-allowed mt-2">
          {initialData ? "Save Changes" : "Create Agent"}
        </button>
      </div>
    </div>
  );
}

function TeamForm({
  initialData,
  onSave,
}: {
  initialData?: { name: string; teamDescription: string; members: Agent[]; contacts: Record<string, Record<string, string>> };
  onSave: (data: { name: string; teamDescription: string; members: Agent[]; contacts: Record<string, Record<string, string>> }) => void;
}) {
  const models = useAppStore((s) => s.models);

  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [teamName, setTeamName] = useState(initialData?.name ?? "");
  const [teamDesc, setTeamDesc] = useState(initialData?.teamDescription ?? "");
  const [members, setMembers] = useState<Agent[]>(initialData?.members ?? []);
  const [contacts, setContacts] = useState<Record<string, Record<string, string>>>(initialData?.contacts ?? {});

  const [editingMemberIdx, setEditingMemberIdx] = useState<number | null>(null);
  const [memberForm, setMemberForm] = useState<{ name: string; modelId: string; role: string; systemPrompt: string; toolNames: string[]; skillNames: string[]; hookEnabled: boolean }>({
    name: "", modelId: models[0]?.id ?? "", role: "", systemPrompt: "", toolNames: [], skillNames: [], hookEnabled: true,
  });

  const openMemberEditor = (idx?: number) => {
    if (idx !== undefined && members[idx]) {
      const m = members[idx];
      setMemberForm({ name: m.name, modelId: m.modelId, role: m.contacts ? Object.values(m.contacts)[0]?.[m.name] ?? "" : "", systemPrompt: m.systemPrompt, toolNames: m.toolNames, skillNames: m.skillNames, hookEnabled: m.hookEnabled });
    } else {
      setMemberForm({ name: "", modelId: models[0]?.id ?? "", role: "", systemPrompt: "", toolNames: [], skillNames: [], hookEnabled: true });
    }
    setEditingMemberIdx(idx ?? null);
  };

  const saveMember = () => {
    const newMember: Agent = {
      id: editingMemberIdx != null && members[editingMemberIdx] ? members[editingMemberIdx].id : crypto.randomUUID(),
      name: memberForm.name || `Member ${(editingMemberIdx ?? members.length) + 1}`,
      type: "single",
      basePath: "",
      modelId: memberForm.modelId,
      systemPrompt: memberForm.systemPrompt,
      toolNames: memberForm.toolNames,
      skillNames: memberForm.skillNames,
      hookEnabled: memberForm.hookEnabled,
      messages: [],
    };
    const updated = editingMemberIdx != null
      ? members.map((m, i) => (i === editingMemberIdx ? newMember : m))
      : [...members, newMember];
    setMembers(updated);
    setEditingMemberIdx(null);
  };

  const removeMember = (idx: number) => {
    setMembers(members.filter((_, i) => i !== idx));
    const name = members[idx].name;
    const newContacts = { ...contacts };
    delete newContacts[name];
    for (const key of Object.keys(newContacts)) {
      const c = { ...newContacts[key] };
      delete c[name];
      newContacts[key] = c;
    }
    setContacts(newContacts);
  };

  const renderStep = () => {
    if (editingMemberIdx !== null) {
      return (
        <div className="p-6 space-y-4">
          <h3 className="text-base font-semibold">{editingMemberIdx < members.length ? "Edit Member" : "Add Member"}</h3>
          <div><label className="block text-sm font-medium mb-1">Name</label>
            <input type="text" value={memberForm.name} onChange={(e) => setMemberForm({ ...memberForm, name: e.target.value })} placeholder="Member name"
              className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]" />
          </div>
          <div><label className="block text-sm font-medium mb-1">Model</label>
            <select value={memberForm.modelId} onChange={(e) => setMemberForm({ ...memberForm, modelId: e.target.value })}
              className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]">
              {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </div>
          <div><label className="block text-sm font-medium mb-1">Role in Team</label>
            <input type="text" value={memberForm.role} onChange={(e) => setMemberForm({ ...memberForm, role: e.target.value })}
              placeholder="e.g. Lead Developer, Researcher, Code Reviewer"
              className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]" />
          </div>
          <div><label className="block text-sm font-medium mb-1">System Prompt</label>
            <textarea value={memberForm.systemPrompt} onChange={(e) => setMemberForm({ ...memberForm, systemPrompt: e.target.value })} rows={3}
              className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring] resize-none" />
          </div>
          <div className="flex gap-2">
            <button onClick={saveMember} className="flex-1 py-2 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] hover:opacity-90 text-sm font-medium">Save Member</button>
            <button onClick={() => setEditingMemberIdx(null)} className="px-4 py-2 rounded-lg border border-[--color-border] hover:bg-[--color-secondary] text-sm">Cancel</button>
          </div>
        </div>
      );
    }

    if (step === 0) {
      return (
        <div className="p-6 space-y-4">
          <h2 className="text-lg font-semibold mb-1">Configure Team</h2>
          <p className="text-sm text-[--color-muted-foreground] mb-6">Set up team info and description</p>
          <div><label className="block text-sm font-medium mb-1.5">Team Name</label>
            <input type="text" value={teamName} onChange={(e) => setTeamName(e.target.value)} placeholder="My Agent Team"
              className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring]" />
          </div>
          <div><label className="block text-sm font-medium mb-1.5">Team Description</label>
            <textarea value={teamDesc} onChange={(e) => setTeamDesc(e.target.value)} placeholder="A collaborative team for full-stack development..." rows={4}
              className="w-full px-3 py-2 rounded-lg border border-[--color-border] bg-white focus:outline-none focus:ring-2 focus:ring-[--color-ring] resize-none" />
          </div>
          <button onClick={() => setStep(1)} disabled={!teamName}
            className="w-full py-2.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] hover:opacity-90 font-medium disabled:opacity-50">Next: Add Members</button>
        </div>
      );
    }

    if (step === 1) {
      return (
        <div className="p-6">
          <h2 className="text-lg font-semibold mb-1">Team Members</h2>
          <p className="text-sm text-[--color-muted-foreground] mb-4">Add and configure team members</p>
          <div className="space-y-2 max-h-[300px] overflow-y-auto mb-4">
            {members.map((m, i) => (
              <div key={m.id} className="flex items-center justify-between p-3 rounded-lg border border-[--color-border] bg-[--color-secondary]/20">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{m.name}</p>
                  <p className="text-xs text-[--color-muted-foreground]">{models.find((mod) => mod.id === m.modelId)?.name ?? "No model"}</p>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => openMemberEditor(i)}
                    className="px-2 py-1 text-xs rounded hover:bg-[--color-secondary] text-[--color-foreground]">Edit</button>
                  <button onClick={() => removeMember(i)}
                    className="px-2 py-1 text-xs rounded hover:bg-red-50 text-[--color-danger]">Remove</button>
                </div>
              </div>
            ))}
          </div>
          <button onClick={() => openMemberEditor()}
            className="w-full py-2.5 rounded-lg border-2 border-dashed border-[--color-border] hover:border-[--color-primary] hover:bg-[--color-primary]/5 transition-all text-sm text-[--color-muted-foreground]">
            + Add Member
          </button>
          <div className="flex gap-2 mt-4">
            <button onClick={() => setStep(0)} className="flex-1 py-2 rounded-lg border border-[--color-border] hover:bg-[--color-secondary] text-sm">Back</button>
            <button onClick={() => setStep(2)} disabled={members.length === 0}
              className="flex-1 py-2.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] hover:opacity-90 font-medium disabled:opacity-50">Next: Configure Contacts</button>
          </div>
        </div>
      );
    }

    return (
      <div className="p-6">
        <h2 className="text-lg font-semibold mb-1">Configure Contacts</h2>
        <p className="text-sm text-[--color-muted-foreground] mb-4">Configure which members can see each other</p>
        <div className="space-y-4 max-h-[350px] overflow-y-auto">
          {members.map((member) => (
            <div key={member.id} className="border border-[--color-border] rounded-lg p-3">
              <p className="text-sm font-medium mb-2">{member.name}&apos;s contacts</p>
              <div className="space-y-1">
                {members.filter((m) => m.id !== member.id).map((other) => {
                  const memberContacts = contacts[member.id] ?? {};
                  const isChecked = other.id in memberContacts;
                  return (
                    <div key={other.id} className="flex items-center gap-2">
                      <input type="checkbox" checked={isChecked}
                        onChange={(e) => {
                          const newContacts = { ...contacts };
                          if (e.target.checked) {
                            newContacts[member.id] = { ...(newContacts[member.id] ?? {}), [other.id]: "" };
                          } else {
                            const c = { ...(newContacts[member.id] ?? {}) };
                            delete c[other.id];
                            newContacts[member.id] = c;
                          }
                          setContacts(newContacts);
                        }}
                        className="rounded" />
                      <span className="text-sm w-32 shrink-0">{other.name}</span>
                      {isChecked && (
                        <input type="text" value={contacts[member.id]?.[other.id] ?? ""}
                          onChange={(e) => {
                            const newContacts = { ...contacts };
                            newContacts[member.id] = { ...(newContacts[member.id] ?? {}), [other.id]: e.target.value };
                            setContacts(newContacts);
                          }}
                          placeholder="role..."
                          className="flex-1 px-2 py-1 text-xs rounded border border-[--color-border] bg-white focus:outline-none focus:ring-1 focus:ring-[--color-ring]" />
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
        <div className="flex gap-2 mt-4">
          <button onClick={() => setStep(1)} className="flex-1 py-2 rounded-lg border border-[--color-border] hover:bg-[--color-secondary] text-sm">Back</button>
          <button onClick={() => onSave({ name: teamName, teamDescription: teamDesc, members, contacts })}
            className="flex-1 py-2.5 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] hover:opacity-90 font-medium">Create Team</button>
        </div>
      </div>
    );
  };

  return <>{renderStep()}</>;
}

export function AgentConfigDialog({ open, onClose, mode, type, agentId }: AgentConfigDialogProps) {
  const agents = useAppStore((s) => s.agents);
  const models = useAppStore((s) => s.models);
  const addAgent = useAppStore((s) => s.addAgent);
  const addTeam = useAppStore((s) => s.addTeam);
  const updateAgent = useAppStore((s) => s.updateAgent);
  const updateTeam = useAppStore((s) => s.updateTeam);
  const [localType, setLocalType] = useState<"agent" | "team" | "">(type);

  useEffect(() => {
    setLocalType(type);
  }, [open, type]);

  const existingAgent = agentId ? agents.find((a) => a.id === agentId) : null;

  if (!open) return null;

  if (!localType && mode === "create") {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center">
        <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
        <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden">
          <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-[--color-secondary] transition-colors z-10"><X size={18} /></button>
          <TypeSelection onSelect={(t) => setLocalType(t)} />
        </div>
      </div>
    );
  }

  const handleSingleSave = (data: { name: string; basePath: string; modelId: string; systemPrompt: string; toolNames: string[]; skillNames: string[]; hookEnabled: boolean }) => {
    if (mode === "edit" && existingAgent) {
      updateAgent(existingAgent.id, data);
    } else {
      addAgent({ id: crypto.randomUUID(), type: "single", messages: [], ...data });
    }
    onClose();
  };

  const handleTeamSave = (data: { name: string; teamDescription: string; members: Agent[]; contacts: Record<string, Record<string, string>> }) => {
    const team: Agent = {
      id: existingAgent?.id ?? crypto.randomUUID(),
      name: data.name,
      type: "team",
      basePath: "",
      modelId: models[0]?.id ?? "",
      systemPrompt: data.teamDescription,
      toolNames: [],
      skillNames: [],
      hookEnabled: true,
      teamDescription: data.teamDescription,
      teamMembers: data.members,
      contacts: data.contacts,
      messages: [],
    };
    if (mode === "edit" && existingAgent) {
      updateTeam(existingAgent.id, team);
    } else {
      addTeam(team);
    }
    onClose();
  };

  const effectiveType = localType || existingAgent?.type || "agent";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/20 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl overflow-hidden">
        <button onClick={onClose} className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-[--color-secondary] transition-colors z-10"><X size={18} /></button>
        {effectiveType === "agent" && (
          <SingleAgentForm
            initialData={existingAgent && existingAgent.type === "single" ? {
              name: existingAgent.name, basePath: existingAgent.basePath, modelId: existingAgent.modelId,
              systemPrompt: existingAgent.systemPrompt, toolNames: existingAgent.toolNames, skillNames: existingAgent.skillNames, hookEnabled: existingAgent.hookEnabled,
            } : undefined}
            onSave={handleSingleSave} />
        )}
        {effectiveType === "team" && (
          <TeamForm
            initialData={existingAgent && existingAgent.type === "team" ? {
              name: existingAgent.name, teamDescription: existingAgent.teamDescription ?? "",
              members: existingAgent.teamMembers ?? [], contacts: existingAgent.contacts ?? {},
            } : undefined}
            onSave={handleTeamSave} />
        )}
      </div>
    </div>
  );
}
