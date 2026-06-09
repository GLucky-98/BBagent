import { useState, useMemo, useCallback, useEffect, useRef } from "react";
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
  getBezierPath,
  MarkerType,
} from "@xyflow/react";
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from "d3-force";
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

// ── Node colors — each node's outgoing edges use this color ──
const NODE_COLORS = [
  "#6366f1", // indigo
  "#10b981", // emerald
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#ef4444", // red
  "#a855f7", // purple
  "#84cc16", // lime
  "#ec4899", // pink
  "#14b8a6", // teal
];

function getNodeColor(index: number): string {
  return NODE_COLORS[index % NODE_COLORS.length];
}

// ── Force-directed layout ──
function layoutWithForce(
  nodes: Node[],
  edges: Edge[],
  width: number,
  height: number,
): Node[] {
  if (nodes.length === 0) return nodes;

  const cx = width / 2 || 300;
  const cy = height / 2 || 250;

  // No edges: arrange in a circle
  if (edges.length === 0) {
    const radius = Math.min(width, height) * 0.3 || 150;
    return nodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2;
      return {
        ...node,
        position: {
          x: cx + radius * Math.cos(angle),
          y: cy + radius * Math.sin(angle),
        },
      };
    });
  }

  // Build simulation data
  const simNodes = nodes.map((n) => ({
    id: n.id,
    x: cx + (Math.random() - 0.5) * 40,
    y: cy + (Math.random() - 0.5) * 40,
  }));

  const simLinks = edges.map((e) => ({
    source: e.source,
    target: e.target,
  }));

  const simulation = forceSimulation(simNodes as d3.SimulationNodeDatum[])
    .force(
      "link",
      forceLink(simLinks as d3.SimulationLinkDatum<d3.SimulationNodeDatum>[])
        .id((d: any) => d.id)
        .distance(160),
    )
    .force("charge", forceManyBody().strength(-500))
    .force("center", forceCenter(cx, cy))
    .force("collide", forceCollide(80))
    .stop();

  simulation.tick(300);

  const posMap = new Map<string, { x: number; y: number }>();
  for (const sn of simNodes) {
    posMap.set(sn.id, { x: (sn as any).x, y: (sn as any).y });
  }

  return nodes.map((node) => {
    const pos = posMap.get(node.id) || { x: cx, y: cy };
    return { ...node, position: pos };
  });
}

// ── Build graph data from team messages ──
function buildGraphData(
  members: any[],
  messages: TeamChatMessage[],
  agentStates: Record<string, string>,
  width: number,
  height: number,
) {
  const nameToId = new Map<string, string>();
  const memberNames = new Set<string>();
  for (const m of members) {
    nameToId.set(m.name, m.id);
    memberNames.add(m.name);
  }

  // Count messages per directed edge
  const edgeMsgCounts = new Map<string, { count: number; latestTs: number }>();

  for (const msg of messages) {
    const srcId = nameToId.get(msg.fromAgent);
    if (!srcId) continue;

    // Determine target agents
    const targets: string[] = [];
    if (msg.type === "broadcast") {
      for (const name of memberNames) {
        if (name !== msg.fromAgent) {
          const tid = nameToId.get(name);
          if (tid) targets.push(tid);
        }
      }
    } else {
      const tgtId = nameToId.get(msg.toAgent);
      if (tgtId) targets.push(tgtId);
    }

    for (const tgtId of targets) {
      const key = `${srcId}->${tgtId}`;
      const existing = edgeMsgCounts.get(key);
      edgeMsgCounts.set(key, {
        count: (existing?.count || 0) + 1,
        latestTs: Math.max(existing?.latestTs || 0, msg.timestamp),
      });
    }
  }

  // Assign color index to each node
  let colorIdx = 0;
  const nodeColorIdx: Record<string, number> = {};

  const rfNodes: Node[] = members.map((m: any) => {
    if (!(m.id in nodeColorIdx)) {
      nodeColorIdx[m.id] = colorIdx++;
    }
    return {
      id: m.id,
      type: "agentNode",
      data: {
        label: m.name,
        state: agentStates[m.id] || m.state || "ready",
        nodeColor: getNodeColor(nodeColorIdx[m.id]),
      },
      position: { x: 0, y: 0 },
    };
  });

  // Build edges with thickness based on message count
  const counts = Array.from(edgeMsgCounts.values()).map((e) => e.count);
  const maxCount = Math.max(...counts, 1);

  const rfEdges: Edge[] = Array.from(edgeMsgCounts.entries()).map(
    ([key, { count, latestTs }]) => {
      const [srcId, tgtId] = key.split("->");
      const thickness = 1.5 + (count / maxCount) * 4.5; // 1.5–6px
      const srcColorIdx = nodeColorIdx[srcId] ?? 0;
      const color = getNodeColor(srcColorIdx);

      return {
        id: `e-${srcId}-${tgtId}`,
        source: srcId,
        target: tgtId,
        type: "messageEdge",
        data: { count, thickness, color, latestTs },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color,
          width: 10 + thickness,
          height: 10 + thickness,
        },
        label: count > 1 ? `${count}` : undefined,
        labelStyle: { fontSize: 9, fill: color, fontWeight: 700 },
        labelBgStyle: { fill: "white", fillOpacity: 0.9, rx: 4, ry: 4 },
        labelBgPadding: [3, 2] as [number, number],
      };
    },
  );

  const layoutedNodes = layoutWithForce(rfNodes, rfEdges, width, height);
  return { nodes: layoutedNodes, edges: rfEdges };
}

// ── Custom Circular Agent Node ──
function AgentNode({
  data,
}: {
  data: { label: string; state: string; nodeColor: string };
}) {
  const stateColor = STATE_COLORS[data.state] || STATE_COLORS.ready;
  const isRunning = data.state === "running";
  const initials = data.label.slice(0, 2).toUpperCase();

  return (
    <div className="flex flex-col items-center" style={{ width: 76 }}>
      <Handle
        type="target"
        position={Position.Top}
        id="t"
        className="!w-1.5 !h-1.5 !bg-slate-300 !border-0"
      />
      <Handle
        type="target"
        position={Position.Left}
        id="l"
        className="!w-1.5 !h-1.5 !bg-slate-300 !border-0"
      />

      <div className="relative">
        <div
          className="w-14 h-14 rounded-full flex items-center justify-center border-[2.5px] shadow-sm transition-all duration-300"
          style={{
            borderColor: stateColor,
            backgroundColor: isRunning ? `${stateColor}15` : "white",
          }}
        >
          <span className="text-[12px] font-bold text-slate-700 select-none">
            {initials}
          </span>
        </div>
        {/* Running pulse ring */}
        {isRunning && (
          <div
            className="absolute inset-[-4px] rounded-full pointer-events-none"
            style={{
              border: `2px solid ${stateColor}`,
              animation: "pulse-ring 2s ease-out infinite",
              opacity: 0.5,
            }}
          />
        )}
      </div>

      <span className="text-[10px] font-medium text-slate-600 mt-1.5 whitespace-nowrap truncate max-w-[76px] text-center">
        {data.label}
      </span>

      <Handle
        type="source"
        position={Position.Bottom}
        id="b"
        className="!w-1.5 !h-1.5 !bg-slate-300 !border-0"
      />
      <Handle
        type="source"
        position={Position.Right}
        id="r"
        className="!w-1.5 !h-1.5 !bg-slate-300 !border-0"
      />
    </div>
  );
}

const nodeTypes = { agentNode: AgentNode };

// ── Custom Edge with variable thickness + glow on active ──
function MessageEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: any) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const color = data?.color || "#64748b";
  const thickness = data?.thickness || 1.5;
  const isActive = data?.isActive || false;

  return (
    <g>
      {/* Glow layer for recently activated edges */}
      {isActive && (
        <path
          d={edgePath}
          fill="none"
          stroke={color}
          strokeWidth={thickness + 8}
          strokeOpacity={0.25}
          style={{ animation: "edge-glow 1.5s ease-out forwards" }}
        />
      )}
      {/* Main edge */}
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke={color}
        strokeWidth={thickness}
        strokeOpacity={0.75}
        markerEnd={markerEnd}
        style={{ transition: "stroke-width 0.3s ease" }}
      />
    </g>
  );
}

const edgeTypes = { messageEdge: MessageEdge };

// ── View mode ──
type ViewMode = "graph" | "list";

// ── Main Component ──
export function TeamGraphView({ width: _width }: { width: number }) {
  const activeAgentId = useAppStore((s) => s.activeAgentId);
  const agents = useAppStore((s) => s.agents);
  const agentStates = useAppStore((s) => s.agentStates);
  const closeTeamGraph = useAppStore((s) => s.closeTeamGraph);
  const teamMessages = useAppStore((s) => s.teamMessages);
  const activeAgent = agents.find((a) => a.id === activeAgentId);

  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 400 });
  const prevEdgeIdsRef = useRef<Set<string>>(new Set());

  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [expandedContacts, setExpandedContacts] = useState<Set<string>>(
    new Set(),
  );
  const [msgLoadCounts, setMsgLoadCounts] = useState<Record<string, number>>(
    {},
  );

  // Observe container size for force layout
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        setDimensions({ width, height });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Card list data
  const members = useMemo(() => {
    if (!activeAgent || !isTeam(activeAgent)) return [];
    return activeAgent.members;
  }, [activeAgent]);

  const messages: TeamChatMessage[] = useMemo(() => {
    if (!activeAgentId) return [];
    return teamMessages[activeAgentId] || [];
  }, [activeAgentId, teamMessages]);

  // Build graph data from messages
  const { nodes: layoutedNodes, edges: graphEdges } = useMemo(() => {
    if (members.length === 0) return { nodes: [], edges: [] };
    return buildGraphData(
      members,
      messages,
      agentStates,
      dimensions.width,
      dimensions.height,
    );
  }, [members, messages, agentStates, dimensions.width, dimensions.height]);

  const [rfNodes, setNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [rfEdges, setEdges, onEdgesChange] = useEdgesState(graphEdges);

  // Sync nodes when data changes
  useEffect(() => {
    setNodes(layoutedNodes);
  }, [layoutedNodes, setNodes]);

  // Sync edges with activation animation for new edges
  useEffect(() => {
    const currentIds = new Set(graphEdges.map((e) => e.id));
    const prevIds = prevEdgeIdsRef.current;
    const newIds = new Set([...currentIds].filter((id) => !prevIds.has(id)));

    if (newIds.size > 0) {
      const enhanced = graphEdges.map((e) => ({
        ...e,
        data: {
          ...e.data,
          isActive: newIds.has(e.id),
        },
      }));
      setEdges(enhanced);

      // Clear active state after animation
      const timer = setTimeout(() => {
        setEdges(
          graphEdges.map((e) => ({ ...e, data: { ...e.data, isActive: false } })),
        );
      }, 1500);
      prevEdgeIdsRef.current = currentIds;
      return () => clearTimeout(timer);
    } else {
      setEdges(graphEdges);
      prevEdgeIdsRef.current = currentIds;
    }
  }, [graphEdges, setEdges]);

  const contacts = useMemo(() => {
    if (!activeAgent || !isTeam(activeAgent))
      return {} as Record<string, Record<string, string>>;
    return activeAgent.contacts || {};
  }, [activeAgent]);

  const toggleAgentExpand = useCallback((name: string) => {
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }, []);

  const toggleContactExpand = useCallback((key: string) => {
    setExpandedContacts((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
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
            onClick={() =>
              setViewMode(viewMode === "graph" ? "list" : "graph")
            }
            className="flex items-center gap-1.5 px-2 py-1 rounded text-[11px] font-medium
                       bg-(--color-secondary) hover:bg-(--color-secondary-hover)
                       text-(--color-foreground) transition-colors"
            title={
              viewMode === "graph"
                ? "Switch to List view"
                : "Switch to Graph view"
            }
          >
            {viewMode === "graph" ? (
              <>
                <LayoutGrid className="w-3.5 h-3.5" /> List
              </>
            ) : (
              <>
                <Network className="w-3.5 h-3.5" /> Graph
              </>
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
      <div className="flex-1 overflow-hidden" ref={containerRef}>
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

      {/* Animations */}
      <style>{`
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.5; }
          100% { transform: scale(1.4); opacity: 0; }
        }
        @keyframes edge-glow {
          0% { stroke-opacity: 0.4; }
          100% { stroke-opacity: 0; }
        }
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
      <Controls showInteractive={false} className="!border-slate-200 !shadow-sm" />
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

  const messages: TeamChatMessage[] = teamId
    ? teamMessages[teamId] || []
    : [];

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
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 9l-7 7-7-7"
                />
              </svg>
            </button>

            {/* Level 2 — Contacts */}
            {isExpanded && (
              <div className="border-t border-(--color-rule-soft) bg-slate-50/50">
                {Object.keys(agentContacts).length === 0 ? (
                  <p className="text-[11px] text-slate-400 px-3 py-2">
                    No contacts
                  </p>
                ) : (
                  Object.entries(agentContacts).map(
                    ([contactName, role]) => {
                      const contactKey = `${member.name}|${contactName}`;
                      const isContactExpanded =
                        expandedContacts.has(contactKey);

                      // Level 3 — Messages for this contact pair
                      const contactMsgs = messages
                        .filter(
                          (m) =>
                            m.fromAgent === member.name &&
                            m.toAgent === contactName,
                        )
                        .sort((a, b) => b.timestamp - a.timestamp);

                      const shownCount =
                        (msgLoadCounts[contactKey] || 0) + MSG_PAGE_SIZE;
                      const visibleMsgs = contactMsgs.slice(0, shownCount);
                      const hasMore = shownCount < contactMsgs.length;

                      return (
                        <div
                          key={contactKey}
                          className="border-t border-(--color-rule-soft)"
                        >
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
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M19 9l-7 7-7-7"
                              />
                            </svg>
                          </button>

                          {/* Level 3 — Messages */}
                          {isContactExpanded && (
                            <div className="border-t border-(--color-rule-soft) bg-white">
                              {visibleMsgs.length === 0 ? (
                                <p className="text-[10px] text-slate-400 px-3 py-2">
                                  No messages yet
                                </p>
                              ) : (
                                visibleMsgs.map((msg, idx) => {
                                  const time = new Date(
                                    msg.timestamp * 1000,
                                  ).toLocaleTimeString([], {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                  });
                                  const preview =
                                    msg.content.length > 60
                                      ? msg.content.slice(0, 59) + "…"
                                      : msg.content;
                                  const typeTag =
                                    msg.type === "broadcast" ? "[B]" : "";

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
                    },
                  )
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
