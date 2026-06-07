import { useState } from "react";
import { Sparkles, MapPin, ExternalLink, FolderOpen, Trash2, RefreshCw, Check } from "lucide-react";
import { useAppStore } from "../store";
import { cn } from "../lib/utils";
import { FolderPickerModal } from "./FolderPickerModal";
import { api } from "../lib/api";

const ACTIVE_CLASS = "bg-(--color-primary)/10 text-(--color-primary) font-semibold shadow-[inset_4px_0_0_0_#3b82f6]";

function SkillList() {
  const skills = useAppStore((s) => s.skills);
  const selectedSkillId = useAppStore((s) => s.selectedSkillId);
  const setSelectedSkillId = useAppStore((s) => s.setSelectedSkillId);
  const importSkills = useAppStore((s) => s.importSkills);
  const deleteSkill = useAppStore((s) => s.deleteSkill);
  const refreshSkill = useAppStore((s) => s.refreshSkill);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [refreshedId, setRefreshedId] = useState<string | null>(null);

  const handleImport = async (path: string) => {
    setImporting(true);
    try {
      await importSkills(path);
    } catch (e: any) {
      useAppStore.getState().addToast(`Skill import failed: ${e.message || e}`, "warning");
    } finally {
      setImporting(false);
    }
  };

  const handleRefresh = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setRefreshingId(id);
    try {
      await refreshSkill(id);
      setRefreshedId(id);
      setTimeout(() => setRefreshedId(null), 1500);
    } finally {
      setRefreshingId(null);
    }
  };

  const handleDelete = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    deleteSkill(id);
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
              <div
                key={skill.id || skill.name}
                onClick={() => setSelectedSkillId(skill.id || skill.name)}
                className={cn(
                  "w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left transition-all hover:bg-(--color-secondary) cursor-pointer group",
                  selectedSkillId === (skill.id || skill.name) && ACTIVE_CLASS,
                )}
              >
                <div className="w-6 h-6 rounded-lg bg-(--color-primary)/10 text-(--color-primary) flex items-center justify-center shrink-0"><Sparkles size={12} /></div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{skill.name}</p>
                  <p className="text-xs text-(--color-muted-foreground) mt-0.5 line-clamp-2">{skill.description}</p>
                </div>
                <div className="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    className="p-1 rounded hover:bg-(--color-secondary) text-(--color-muted-foreground) hover:text-(--color-primary) disabled:opacity-50"
                    onClick={(e) => handleRefresh(skill.id, e)}
                    disabled={refreshingId === skill.id}
                    title="Refresh skill"
                  >
                    {refreshedId === skill.id ? (
                      <Check size={13} className="text-green-500" />
                    ) : (
                      <RefreshCw size={13} className={refreshingId === skill.id ? "animate-spin" : ""} />
                    )}
                  </button>
                  <button
                    className="p-1 rounded hover:bg-red-50 text-(--color-muted-foreground) hover:text-red-500"
                    onClick={(e) => handleDelete(skill.id, e)}
                    title="Delete skill"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
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
  const selectedSkill = skills.find((s) => (s.id || s.name) === selectedSkillId);

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
          <div><h2 className="font-semibold text-sm">{selectedSkill.name}</h2></div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div>
          <h3 className="text-xs font-medium mb-1 flex items-center gap-1.5"><MapPin size={12} />Local Path</h3>
          <div className="bg-white rounded border border-(--color-border) p-2 flex items-center gap-2">
            <code className="text-xs font-mono flex-1 truncate">{selectedSkill.path}</code>
            <button
              className="p-0.5 rounded hover:bg-(--color-secondary) transition-colors shrink-0"
              onClick={() => selectedSkill.path && api.openPath(selectedSkill.path)}
              title="Open in Finder"
            >
              <ExternalLink className="w-3.5 h-3.5 text-(--color-muted-foreground)" />
            </button>
          </div>
        </div>
        <div>
          <h3 className="text-xs font-medium mb-1">Description</h3>
          <div className="bg-white rounded border border-(--color-border) p-2"><p className="text-xs">{selectedSkill.description}</p></div>
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
