import { useState, useMemo, useCallback, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  Position,
  Handle,
  getSmoothStepPath,
} from "@xyflow/react";
import dagre from "dagre";
import "@xyflow/react/dist/style.css";
import { LayoutGrid, Network, X, MoreHorizontal } from "lucide-react";
import { useAppStore } from "../../store";
import { isTeam, type TeamChatMessage } from "../../types";

// ── State colors ──
const STATE_COLORS: Record<string, string> = {
  running: "#22c55e",
  waiting: "#22c55e",
  error: "#ef4444",
  ready: "#94a3b8",
};

const STATE_BG: Record<string, string> = {
  running: "#f0fdf4",
  waiting: "#f0fdf4",
  error: "#fef2f2",
  ready: "#f1f5f9",
};

const STATE_LABEL: Record<string, string> = {
  running: "Running",
  waiting: "Waiting",
  error: "Error",
  ready: "Ready",
};

// ── Soft edge colors (one per source node) ──
const EDGE_COLORS = [
  "#a5b4fc", // soft indigo
  "#86efac", // soft green
  "#fde68a", // soft amber
  "#c4b5fd", // soft violet
  "#67e8f9", // soft cyan
  "#fca5a5", // soft red
  "#d8b4fe", // soft purple
  "#a3e635", // soft lime
  "#f9a8d4", // soft pink
  "#5eead4", // soft teal
];

function getEdgeColor(index: number): string {
  return EDGE_COLORS[index % EDGE_COLORS.length];
}

// ── Dagre layout for React Flow ──
function layoutWithDagre(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 70, ranksep: 90, marginx: 30, marginy: 30 });

  for (const node of nodes) {
    g.setNode(node.id, { width: 140, height: 60 });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target, {});
  }

  dagre.layout(g);

  return nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - 70, y: pos.y - 30 },
    };
  });
}

// ── Build graph data from team ──
function buildGraphData(
  activeAgent: any,
  agentStates: Record<string, string>,
) {
  const members = activeAgent.members;
  const teamContacts = activeAgent.contacts;

  const nameToId = new Map<string, string>();
  for (const m of members) {
    nameToId.set(m.name, m.id);
  }

  // Detect bidirectional edges
  const edgePairs = new Set<string>();
  for (const [agentName, contactMap] of Object.entries(teamContacts)) {
    for (const contactName of Object.keys(contactMap)) {
      if (agentName === contactName) continue;
      const srcId = nameToId.get(agentName);
      const tgtId = nameToId.get(contactName);
      if (srcId && tgtId) edgePairs.add(`${srcId}->${tgtId}`);
    }
  }

  const rfNodes: Node[] = members.map((m: any) => ({
    id: m.id,
    type: "agentNode",
    data: {
      label: m.name,
      state: agentStates[m.id] || m.state || "ready",
    },
    position: { x: 0, y: 0 },
    sourcePosition: Position.Bottom,
    targetPosition: Position.Top,
  }));

  const rfEdges: Edge[] = [];
  // Assign a color index to each source node for edge coloring
  let colorIdx = 0;
  const nodeColorIdx: Record<string, number> = {};
  for (const [agentName, contactMap] of Object.entries(teamContacts)) {
    const srcId = nameToId.get(agentName);
    if (!srcId) continue;
    if (!(srcId in nodeColorIdx)) {
      nodeColorIdx[srcId] = colorIdx++;
    }
    const edgeColor = getEdgeColor(nodeColorIdx[srcId]);

    for (const [contactName, role] of Object.entries(contactMap)) {
      if (agentName === contactName) continue;
      const tgtId = nameToId.get(contactName);
      if (!tgtId) continue;

      const hasReverse = edgePairs.has(`${tgtId}->${srcId}`);
      const isBidir = hasReverse || edgePairs.has(`${srcId}->${tgtId}`);
      rfEdges.push({
          id: `e-${srcId}-${tgtId}`,
          source: srcId,
          target: tgtId,
          type: "arrowEdge",
          sourceHandle: isBidir ? "r" : "b",
          targetHandle: isBidir ? "l" : "t",
          data: { role, color: edgeColor },
          label: role || undefined,
          labelStyle: { fontSize: 10, fill: "#475569", fontWeight: 500 },
          labelBgStyle: { fill: "white", fillOpacity: 0.9, rx: 3, ry: 3 },
          labelBgPadding: [4, 2] as [number, number],
        });
    }
  }

  return { nodes: layoutWithDagre(rfNodes, rfEdges), edges: rfEdges };
}

// ── Custom Agent Node Component ──
function AgentNode({ data }: { data: { label: string; state: string } }) {
  const color = STATE_COLORS[data.state] || STATE_COLORS.ready;
  const bg = STATE_BG[data.state] || STATE_BG.ready;
  const isRunning = data.state === "running";

  return (
    <div
      className="flex items-center gap-2 px-3 py-2 rounded-lg border-2 bg-white shadow-sm min-w-[120px] relative"
      style={{ borderColor: color, backgroundColor: bg }}
    >
      <Handle type="target" position={Position.Top} id="t" className="!bg-slate-400 !w-2 !h-2" />
      <Handle type="target" position={Position.Left} id="l" className="!bg-slate-400 !w-2 !h-2" />
      <div
        className="w-2.5 h-2.5 rounded-full shrink-0"
        style={{
          backgroundColor: color,
          boxShadow: isRunning ? `0 0 6px ${color}` : "none",
          animation: isRunning ? "pulse-dot 2s ease-in-out infinite" : "none",
        }}
      />
      <span className="text-[12px] font-medium text-slate-800 truncate">
        {data.label}
      </span>
      <Handle type="source" position={Position.Bottom} id="b" className="!bg-slate-400 !w-2 !h-2" />
      <Handle type="source" position={Position.Right} id="r" className="!bg-slate-400 !w-2 !h-2" />
    </div>
  );
}

const nodeTypes = { agentNode: AgentNode };

// ── Custom Edge with mid-arrow ──
function ArrowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  style,
}: any) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  // Compute midpoint direction for arrow placement
  // Use the path midpoint approximation
  const midX = (sourceX + targetX) / 2;
  const midY = (sourceY + targetY) / 2;
  const angle = Math.atan2(targetY - sourceY, targetX - sourceX) * (180 / Math.PI);
  const color = data?.color || "#64748b";

  return (
    <>
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke={color}
        strokeWidth={2}
      />
      {/* Arrow at midpoint — chevron shape ">" */}
      <path
        d={`M${midX - 6},${midY - 4} L${midX + 6},${midY} L${midX - 6},${midY + 4}`}
        fill="none"
        stroke={color}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </>
  );
}

const edgeTypes = { arrowEdge: ArrowEdge };

// ── View mode ──
type ViewMode = "graph" | "list";

// ── Main Component ──
export function TeamGraphView({ width }: { width: number }) {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const agents = useAppStore((s) => s.agents);
  const agentStates = useAppStore((s) => s.agentStates);
  const closeTeamGraph = useAppStore((s) => s.closeTeamGraph);
  const activeAgent = agents.find((a) => a.id === activeAgentId);

  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [expandedContacts, setExpandedContacts] = useState<Set<string>>(new Set());
  const [msgLoadCounts, setMsgLoadCounts] = useState<Record<string, number>>({});

  // Build graph data
  const { nodes: layoutedNodes, edges: graphEdges } = useMemo(() => {
    if (!activeAgent || !isTeam(activeAgent)) return { nodes: [], edges: [] };
    return buildGraphData(activeAgent, agentStates);
  }, [activeAgent, agentStates]);

  const [rfNodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [rfEdges, setEdges, onEdgesChange] = useEdgesState(graphEdges);

  // Sync nodes/edges when data changes (e.g. switching teams)
  useEffect(() => {
    setNodes(layoutedNodes);
  }, [layoutedNodes, setNodes]);

  useEffect(() => {
    setEdges(graphEdges);
  }, [graphEdges, setEdges]);

  // Card list data
  const members = useMemo(() => {
    if (!activeAgent || !isTeam(activeAgent)) return [];
    return activeAgent.members;
  }, [activeAgent]);

  const contacts = useMemo(() => {
    if (!activeAgent || !isTeam(activeAgent)) return {} as Record<string, Record<string, string>>;
    return activeAgent.contacts || {};
  }, [activeAgent]);

  const toggleAgentExpand = useCallback((name: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name); else next.add(name);
      return next;
    });
  }, []);

  const toggleContactExpand = useCallback((key: string) => {
    setExpandedContacts((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }, []);

  const loadMoreMessages = useCallback((key: string) => {
    setMsgLoadCounts((prev) => ({
      ...prev,
      [key]: (prev[key] || 0) + 30,
    }));
  }, []);

  if (!activeAgent || !isTeam(activeAgent) || members.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-(--color-ink-3) text-sm">
        No team selected
      </div>
    );
  }

  return (
    <div className="h-full w-full flex flex-col bg-(--color-background)">
      {/* Header with toggle + close */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-(--color-rule-soft) shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode(viewMode === "graph" ? "list" : "graph")}
            className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-medium
                       bg-(--color-secondary) hover:bg-(--color-secondary-hover)
                       text-(--color-foreground) transition-colors"
            title={viewMode === "graph" ? "Switch to List view" : "Switch to Graph view"}
          >
            {viewMode === "graph" ? (
              <><LayoutGrid className="w-3.5 h-3.5" /> List</>
            ) : (
              <><Network className="w-3.5 h-3.5" /> Graph</>
            )}
          </button>
          <span className="text-[11px] text-(--color-ink-3)">
            {members.length} agents, {graphEdges.length} connections
          </span>
        </div>
        <button
          onClick={closeTeamGraph}
          className="p-1 rounded hover:bg-(--color-secondary) text-(--color-ink-3) transition-colors"
          title="关闭"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {viewMode === "graph" ? (
          <GraphView
            nodes={rfNodes}
            edges={rfEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
          />
        ) : (
          <ListView
            members={members}
            contacts={contacts}
            agentStates={agentStates}
            expandedAgents={expandedAgents}
            expandedContacts={expandedContacts}
            msgLoadCounts={msgLoadCounts}
            onToggleAgent={toggleAgentExpand}
            onToggleContact={toggleContactExpand}
            onLoadMore={loadMoreMessages}
          />
        )}
      </div>

      {/* Pulse animation keyframes */}
      <style>{`
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>
    </div>
  );
}

// ── Graph View (React Flow) ──
function GraphView({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
}: {
  nodes: Node[];
  edges: Edge[];
  onNodesChange: any;
  onEdgesChange: any;
}) {
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      proOptions={{ hideAttribution: true }}
      minZoom={0.3}
      maxZoom={2}
      className="bg-(--color-background)"
    >
      <Background color="#e2e8f0" gap={20} size={1} />
      <Controls
        showInteractive={false}
        className="!border-slate-200 !shadow-sm"
      />
    </ReactFlow>
  );
}

// ── List View (Card List with 3-level expand) ──
const MSG_PAGE_SIZE = 30;

function ListView({
  members,
  contacts,
  agentStates,
  expandedAgents,
  expandedContacts,
  msgLoadCounts,
  onToggleAgent,
  onToggleContact,
  onLoadMore,
}: {
  members: any[];
  contacts: Record<string, Record<string, string>>;
  agentStates: Record<string, string>;
  expandedAgents: Set<string>;
  expandedContacts: Set<string>;
  msgLoadCounts: Record<string, number>;
  onToggleAgent: (name: string) => void;
  onToggleContact: (key: string) => void;
  onLoadMore: (key: string) => void;
}) {
  const teamMessages = useAppStore((s) => s.teamMessages);
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const scrollToTeamMessage = useAppStore((s) => s.scrollToTeamMessage);
  const teamId = activeAgentId || "";

  const messages: TeamChatMessage[] = teamId ? (teamMessages[teamId] || []) : [];

  return (
    <div className="h-full overflow-y-auto p-3 space-y-2">
      {members.map((member: any) => {
        const state = agentStates[member.id] || member.state || "ready";
        const color = STATE_COLORS[state] || STATE_COLORS.ready;
        const bg = STATE_BG[state] || STATE_BG.ready;
        const isExpanded = expandedAgents.has(member.name);
        const agentContacts = contacts[member.name] || {};

        return (
          <div
            key={member.id}
            className="rounded-lg border border-(--color-rule-soft) bg-white overflow-hidden"
          >
            {/* Level 1 — Agent header */}
            <button
              onClick={() => onToggleAgent(member.name)}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left
                         hover:bg-(--color-secondary) transition-colors"
            >
              <div
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ backgroundColor: color }}
              />
              <span className="text-[12px] font-medium text-slate-800 flex-1">
                {member.name}
              </span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                style={{ backgroundColor: bg, color }}
              >
                {STATE_LABEL[state] || state}
              </span>
              <svg
                className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                fill="none" viewBox="0 0 24 24" stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>

            {/* Level 2 — Contacts */}
            {isExpanded && (
              <div className="border-t border-(--color-rule-soft) bg-slate-50/50">
                {Object.keys(agentContacts).length === 0 ? (
                  <p className="text-[11px] text-slate-400 px-3 py-2">No contacts</p>
                ) : (
                  Object.entries(agentContacts).map(([contactName, role]) => {
                    const contactKey = `${member.name}|${contactName}`;
                    const isContactExpanded = expandedContacts.has(contactKey);

                    // Level 3 — Messages for this contact pair
                    const contactMsgs = messages
                      .filter((m) =>
                        m.fromAgent === member.name &&
                        m.toAgent === contactName
                      )
                      .sort((a, b) => b.timestamp - a.timestamp);

                    const shownCount = (msgLoadCounts[contactKey] || 0) + MSG_PAGE_SIZE;
                    const visibleMsgs = contactMsgs.slice(0, shownCount);
                    const hasMore = shownCount < contactMsgs.length;

                    return (
                      <div key={contactKey} className="border-t border-(--color-rule-soft)">
                        {/* Level 2 — Contact row */}
                        <button
                          onClick={() => onToggleContact(contactKey)}
                          className="w-full flex items-center gap-2 px-3 py-2 text-left
                                     hover:bg-slate-100/70 transition-colors"
                        >
                          <span className="font-medium text-[11px] text-slate-600 w-20 shrink-0 truncate">
                            {contactName}
                          </span>
                          <span className="text-[11px] text-slate-400 truncate flex-1">
                            {role || "—"}
                          </span>
                          <span className="text-[10px] text-slate-300 tabular-nums">
                            {contactMsgs.length}
                          </span>
                          <svg
                            className={`w-3 h-3 text-slate-400 transition-transform ${isContactExpanded ? "rotate-180" : ""}`}
                            fill="none" viewBox="0 0 24 24" stroke="currentColor"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>

                        {/* Level 3 — Messages */}
                        {isContactExpanded && (
                          <div className="border-t border-(--color-rule-soft) bg-white">
                            {visibleMsgs.length === 0 ? (
                              <p className="text-[10px] text-slate-400 px-3 py-2">No messages yet</p>
                            ) : (
                              visibleMsgs.map((msg, idx) => {
                                const time = new Date(msg.timestamp * 1000).toLocaleTimeString([], {
                                  hour: "2-digit", minute: "2-digit",
                                });
                                const preview = msg.content.length > 60
                                  ? msg.content.slice(0, 59) + "…"
                                  : msg.content;
                                const typeTag = msg.type === "broadcast" ? "[B]" : "";

                                return (
                                  <button
                                    key={`${msg.timestamp}-${idx}`}
                                    onClick={() =>
                                      scrollToTeamMessage({
                                        timestamp: msg.timestamp,
                                        fromAgent: msg.fromAgent,
                                        toAgent: msg.toAgent,
                                      })
                                    }
                                    className="w-full flex items-start gap-2 px-3 py-1.5 text-left
                                               hover:bg-blue-50/60 transition-colors border-b
                                               border-(--color-rule-soft) last:border-b-0"
                                  >
                                    <span className="text-[10px] text-slate-400 tabular-nums shrink-0 mt-px">
                                      {time}
                                    </span>
                                    {typeTag && (
                                      <span className="text-[9px] text-amber-500 font-semibold shrink-0 mt-px">
                                        {typeTag}
                                      </span>
                                    )}
                                    <span className="text-[11px] text-slate-600 truncate flex-1">
                                      {preview}
                                    </span>
                                  </button>
                                );
                              })
                            )}
                            {hasMore && (
                              <button
                                onClick={() => onLoadMore(contactKey)}
                                className="w-full flex items-center justify-center py-1.5
                                           hover:bg-slate-50 transition-colors"
                              >
                                <MoreHorizontal className="w-4 h-4 text-slate-400" />
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
