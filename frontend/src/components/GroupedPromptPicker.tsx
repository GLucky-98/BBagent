import { useState } from "react";
import { Search, ChevronRight, FolderClosed } from "lucide-react";
import { cn } from "../lib/utils";
import type { Prompt } from "../types";

/** Group prompts by their `group` field */
function groupPrompts(prompts: Prompt[]) {
  const ungrouped: Prompt[] = [];
  const groupMap = new Map<string, Prompt[]>();
  for (const p of prompts) {
    if (!p.group) {
      ungrouped.push(p);
    } else {
      const list = groupMap.get(p.group) ?? [];
      list.push(p);
      groupMap.set(p.group, list);
    }
  }
  const groups = Array.from(groupMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([name, prompts]) => ({ name, prompts }));
  return { ungrouped, groups };
}

interface GroupedPromptPickerProps {
  prompts: Prompt[];
  onSelect: (prompt: Prompt) => void;
  maxHeight?: string;
}

/**
 * A reusable prompt picker that shows prompts grouped by their `group` field.
 * - When searching (filter non-empty): flat list of matching prompts
 * - When browsing (filter empty): grouped collapsible view
 */
export function GroupedPromptPicker({ prompts, onSelect, maxHeight = "120px" }: GroupedPromptPickerProps) {
  const [filter, setFilter] = useState("");
  const [showAll, setShowAll] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const toggleGroup = (name: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  };

  const isSearching = filter.trim() !== "";

  // When searching, show flat filtered list
  const filteredPrompts = isSearching
    ? prompts.filter(
        (p) =>
          p.name.toLowerCase().includes(filter.toLowerCase()) ||
          p.content.toLowerCase().includes(filter.toLowerCase())
      )
    : showAll
      ? prompts
      : [];

  // When browsing (no filter), show grouped view
  const { ungrouped, groups } = isSearching ? { ungrouped: [], groups: [] } : groupPrompts(prompts);

  const hasNoResults = isSearching
    ? filteredPrompts.length === 0
    : ungrouped.length === 0 && groups.length === 0;

  return (
    <div className="border border-(--color-border) rounded-lg overflow-hidden">
      <div className="flex items-center gap-1 px-3 py-2 border-b border-(--color-border) bg-(--color-muted)/20">
        <Search className="w-3 h-3 text-(--color-muted-foreground) shrink-0" />
        <input
          type="text"
          value={filter}
          onChange={(e) => { setFilter(e.target.value); if (!e.target.value.trim()) setShowAll(false); }}
          placeholder="Search by prompt title..."
          className="flex-1 text-xs bg-transparent outline-none"
        />
        {!isSearching && (
          <button
            type="button"
            onClick={() => { setShowAll(!showAll); setFilter(""); }}
            className="text-[10px] px-1.5 py-0.5 rounded border border-(--color-border) hover:bg-(--color-secondary) shrink-0"
          >
            {showAll ? "Search" : "Browse All"}
          </button>
        )}
      </div>
      <div className="overflow-y-auto" style={{ maxHeight }}>
        {prompts.length === 0 ? (
          <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No prompts available</div>
        ) : hasNoResults ? (
          <div className="px-3 py-4 text-center text-xs text-(--color-muted-foreground)">No matching prompts found</div>
        ) : isSearching || showAll ? (
          // Flat list (search or browse-all mode)
          (isSearching ? filteredPrompts : prompts).map((p) => (
            <button
              key={p.id}
              type="button"
              className="w-full text-left px-3 py-2 hover:bg-(--color-secondary) text-sm"
              onClick={() => onSelect(p)}
            >
              <span className="font-medium">{p.name}</span>
              {p.group && <span className="text-[10px] text-(--color-muted-foreground) ml-1.5">{p.group}</span>}
            </button>
          ))
        ) : (
          // Grouped view
          <div className="py-1">
            {ungrouped.map((p) => (
              <button
                key={p.id}
                type="button"
                className="w-full text-left px-3 py-2 hover:bg-(--color-secondary) text-sm"
                onClick={() => onSelect(p)}
              >
                <span className="font-medium">{p.name}</span>
              </button>
            ))}
            {groups.map((g) => {
              const collapsed = collapsedGroups.has(g.name);
              return (
                <div key={g.name}>
                  <div
                    className="flex items-center gap-1.5 px-3 py-1.5 hover:bg-(--color-secondary) cursor-pointer select-none"
                    onClick={() => toggleGroup(g.name)}
                  >
                    <ChevronRight size={12} className={cn("transition-transform shrink-0", !collapsed && "rotate-90")} />
                    <FolderClosed size={12} className="text-amber-500 shrink-0" />
                    <span className="text-xs font-medium">{g.name}</span>
                    <span className="text-[10px] text-(--color-muted-foreground) ml-auto">{g.prompts.length}</span>
                  </div>
                  {!collapsed && g.prompts.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className="w-full text-left pl-8 pr-3 py-2 hover:bg-(--color-secondary) text-sm"
                      onClick={() => onSelect(p)}
                    >
                      <span className="font-medium">{p.name}</span>
                    </button>
                  ))}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
