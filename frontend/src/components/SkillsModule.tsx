import { useState } from "react";
import { Sparkles, MapPin, FileText, Info, FolderOpen } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import { FolderPickerModal } from "./FolderPickerModal";

function SkillList() {
  const skills = useAppStore((s) => s.skills);
  const selectedSkillId = useAppStore((s) => s.selectedSkillId);
  const setSelectedSkillId = useAppStore((s) => s.setSelectedSkillId);
  const importSkills = useAppStore((s) => s.importSkills);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);

  const handleImport = async (path: string) => {
    setImporting(true);
    try {
      await importSkills(path);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="w-[300px] h-full bg-white border-r border-(--color-border) flex flex-col">
      <div className="p-3 border-b border-(--color-border)">
        <button
          onClick={() => setImportModalOpen(true)}
          disabled={importing}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-(--color-border) text-sm hover:bg-(--color-secondary) disabled:opacity-50"
        >
          <FolderOpen size={16} />
          {importing ? "Importing..." : "Import from Folder"}
        </button>
      </div>

      <FolderPickerModal
        open={importModalOpen}
        onClose={() => setImportModalOpen(false)}
        onSelect={handleImport}
        title="Select Skills Folder"
      />

      <div className="flex-1 overflow-y-auto p-2">
        {skills.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-(--color-muted-foreground)">
            <Sparkles size={32} className="mb-2 opacity-50" /><p className="text-sm">No skills found</p>
          </div>
        ) : (
          <div className="space-y-1">
            {skills.map((skill) => (
              <button key={skill.name} onClick={() => setSelectedSkillId(skill.name)}
                className={cn("w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-(--color-secondary)", selectedSkillId === skill.name && "bg-(--color-primary)/10 text-(--color-primary) font-semibold shadow-[inset_4px_0_0_0_#10b981]")}>
                <div className="w-6 h-6 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center shrink-0"><Sparkles size={12} /></div>
                <div className="flex-1 min-w-0"><p className="text-sm font-medium truncate">{skill.name}</p><p className="text-xs text-(--color-muted-foreground) mt-0.5 line-clamp-2">{skill.description}</p></div>
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
  const selectedSkill = skills.find((s) => s.name === selectedSkillId);

  if (!selectedSkill) {
    return (
      <div className="flex-1 h-full flex flex-col items-center justify-center bg-(--color-background) text-(--color-muted-foreground)">
        <Sparkles size={48} className="mb-4 opacity-30" /><p className="text-lg font-medium">No skill selected</p><p className="text-sm mt-1">Select a skill to view details</p>
      </div>
    );
  }

  return (
    <div className="flex-1 h-full flex flex-col bg-(--color-background)">
      <header className="px-4 py-3 bg-white border-b border-(--color-border)">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center"><Sparkles size={16} /></div>
          <div><h2 className="font-semibold text-sm">{selectedSkill.name}</h2><p className="text-xs text-(--color-muted-foreground)">{selectedSkill.metadata.version && `v${selectedSkill.metadata.version}`}{selectedSkill.metadata.license && ` \u2022 ${selectedSkill.metadata.license}`}</p></div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <h3 className="text-xs font-medium mb-1 flex items-center gap-1.5"><MapPin size={12} />Local Path</h3>
          <div className="bg-white rounded border border-(--color-border) p-2"><code className="text-xs font-mono">{selectedSkill.path}</code></div>
        </div>
        <div>
          <h3 className="text-xs font-medium mb-1 flex items-center gap-1.5"><Info size={12} />Metadata</h3>
          <div className="bg-white rounded border border-(--color-border) p-2 grid grid-cols-2 gap-2 text-xs">
            {selectedSkill.metadata.version && <div><span className="text-(--color-muted-foreground)">Version:</span><span className="ml-1 font-medium">{selectedSkill.metadata.version}</span></div>}
            {selectedSkill.metadata.license && <div><span className="text-(--color-muted-foreground)">License:</span><span className="ml-1 font-medium">{selectedSkill.metadata.license}</span></div>}
            {selectedSkill.metadata.allowedTools && selectedSkill.metadata.allowedTools.length > 0 && (
              <div className="col-span-2"><span className="text-(--color-muted-foreground)">Allowed Tools:</span><div className="mt-1 flex flex-wrap gap-1">{selectedSkill.metadata.allowedTools.map((t) => <span key={t} className="px-1.5 py-0.5 bg-(--color-secondary) text-xs rounded">{t}</span>)}</div></div>
            )}
          </div>
        </div>
        <div>
          <h3 className="text-xs font-medium mb-1 flex items-center gap-1.5"><FileText size={12} />Description</h3>
          <div className="bg-white rounded border border-(--color-border) p-2"><p className="text-xs">{selectedSkill.description}</p></div>
        </div>
        <div>
          <h3 className="text-xs font-medium mb-1">Skill Body</h3>
          <div className="bg-white rounded border border-(--color-border) p-2"><pre className="text-xs whitespace-pre-wrap font-mono leading-relaxed">{selectedSkill.body}</pre></div>
        </div>
      </div>
    </div>
  );
}

export function SkillsModule() {
  return (
    <div className="flex h-full">
      <SkillList />
      <SkillDetailPanel />
    </div>
  );
}
