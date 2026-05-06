import { Sparkles, MapPin, FileText, Info } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";

function SkillList() {
  const skills = useAppStore((s) => s.skills);
  const selectedSkillId = useAppStore((s) => s.selectedSkillId);
  const setSelectedSkillId = useAppStore((s) => s.setSelectedSkillId);

  return (
    <div className="w-[320px] h-screen bg-white border-r border-[--color-border] flex flex-col">
      <div className="p-3 border-b border-[--color-border]">
        <div className="h-10 flex items-center px-3">
          <span className="text-sm font-medium text-[--color-muted-foreground]">
            {skills.length} skills available
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-[--color-muted-foreground]">
            <Sparkles size={32} className="mb-2 opacity-50" />
            <p className="text-sm">No skills found</p>
          </div>
        ) : (
          <div className="space-y-1">
            {skills.map((skill) => (
              <button
                key={skill.id}
                onClick={() => setSelectedSkillId(skill.id)}
                className={cn(
                  "w-full flex items-start gap-3 px-3 py-3 rounded-lg text-left transition-all duration-150",
                  "hover:bg-[--color-secondary]",
                  selectedSkillId === skill.id && "bg-[--color-primary]/10 text-[--color-primary]"
                )}
              >
                <div className="w-8 h-8 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center shrink-0">
                  <Sparkles size={14} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{skill.name}</p>
                  <p className="text-xs text-[--color-muted-foreground] mt-0.5 line-clamp-2">
                    {skill.description}
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

function SkillDetailPanel() {
  const skills = useAppStore((s) => s.skills);
  const selectedSkillId = useAppStore((s) => s.selectedSkillId);

  const selectedSkill = skills.find((s) => s.id === selectedSkillId);

  if (!selectedSkill) {
    return (
      <div className="flex-1 h-screen flex flex-col items-center justify-center bg-[--color-background] text-[--color-muted-foreground]">
        <Sparkles size={48} className="mb-4 opacity-30" />
        <p className="text-lg font-medium">No skill selected</p>
        <p className="text-sm mt-1">Select a skill to view details</p>
      </div>
    );
  }

  return (
    <div className="flex-1 h-screen flex flex-col bg-[--color-background]">
      <header className="px-6 py-4 bg-white border-b border-[--color-border]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-[--color-primary]/10 text-[--color-primary] flex items-center justify-center">
            <Sparkles size={20} />
          </div>
          <div>
            <h2 className="font-semibold text-[--color-foreground]">
              {selectedSkill.name}
            </h2>
            <p className="text-xs text-[--color-muted-foreground]">
              {selectedSkill.metadata.version && `v${selectedSkill.metadata.version}`}
              {selectedSkill.metadata.license && ` • ${selectedSkill.metadata.license}`}
            </p>
          </div>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto space-y-6">
          <div>
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <MapPin size={14} />
              Local Path
            </h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <code className="text-sm font-mono text-[--color-foreground]">
                {selectedSkill.path}
              </code>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <Info size={14} />
              Metadata
            </h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                {selectedSkill.metadata.license && (
                  <div>
                    <span className="text-[--color-muted-foreground]">License:</span>
                    <span className="ml-2 font-medium">{selectedSkill.metadata.license}</span>
                  </div>
                )}
                {selectedSkill.metadata.version && (
                  <div>
                    <span className="text-[--color-muted-foreground]">Version:</span>
                    <span className="ml-2 font-medium">{selectedSkill.metadata.version}</span>
                  </div>
                )}
                {selectedSkill.metadata.compatibility && (
                  <div className="col-span-2">
                    <span className="text-[--color-muted-foreground]">Compatibility:</span>
                    <span className="ml-2 font-medium">{selectedSkill.metadata.compatibility}</span>
                  </div>
                )}
                {selectedSkill.metadata.allowedTools &&
                  selectedSkill.metadata.allowedTools.length > 0 && (
                    <div className="col-span-2">
                      <span className="text-[--color-muted-foreground]">Allowed Tools:</span>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {selectedSkill.metadata.allowedTools.map((tool) => (
                          <span
                            key={tool}
                            className="px-2 py-0.5 bg-[--color-secondary] text-xs rounded"
                          >
                            {tool}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
              </div>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
              <FileText size={14} />
              Description
            </h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <p className="text-sm text-[--color-foreground]">
                {selectedSkill.description}
              </p>
            </div>
          </div>

          <div>
            <h3 className="text-sm font-medium mb-2">Skill Body</h3>
            <div className="bg-white rounded-lg border border-[--color-border] p-4">
              <pre className="text-sm whitespace-pre-wrap text-[--color-foreground] font-mono leading-relaxed">
                {selectedSkill.body}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function SkillsModule() {
  return (
    <>
      <SkillList />
      <SkillDetailPanel />
    </>
  );
}
