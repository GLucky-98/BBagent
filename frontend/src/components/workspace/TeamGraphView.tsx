import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import { useShallow } from "zustand/react/shallow";
import {
  ReactFlow,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  EdgeLabelRenderer,
  type Node,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Activity,
  ChevronDown,
  GitBranch,
  History,
  List,
  MessageSquare,
  MoreHorizontal,
  Pause,
  Play,
  Radio,
  SkipBack,
  SkipForward,
  Users,
  X,
} from "lucide-react";
import { cn } from "../../lib/utils";
import { useAppStore } from "../../store";
import { isTeam, type SingleAgent, type TeamChatMessage } from "../../types";

type AgentState = "ready" | "waiting" | "running" | "error";
type ViewMode = "structure" | "activity" | "replay" | "list";
type RelationFocus = "incoming" | "outgoing" | "bidirectional" | null;
type Selection =
  | { type: "node"; id: string }
  | { type: "edge"; id: string }
  | null;

interface TeamNodeData extends Record<string, unknown> {
  label: string;
  state: AgentState;
  color: string;
  anchorPosition: Position;
  anchorOffset: { x: number; y: number };
  contactOutCount: number;
  contactInCount: number;
  sentCount: number;
  receivedCount: number;
  latestTs?: number;
  selected: boolean;
  dimmed: boolean;
}

interface RecentMessage {
  fromAgent: string;
  toAgent: string;
  content: string;
  type: TeamChatMessage["type"];
  timestamp: number;
}

interface TeamEdgeData extends Record<string, unknown> {
  mode: ViewMode;
  color: string;
  label: string;
  roleForward?: string;
  roleReverse?: string;
  sourceName: string;
  targetName: string;
  bidirectional: boolean;
  activityOnly: boolean;
  messageCount: number;
  latestTs?: number;
  latestMessage?: RecentMessage;
  recentMessages: RecentMessage[];
  sourceAnchor: { x: number; y: number };
  targetAnchor: { x: number; y: number };
  thickness: number;
  pulseCount: number;
  relationFocus: RelationFocus;
  active: boolean;
  selected: boolean;
  dimmed: boolean;
}

interface TeamRelation {
  id: string;
  source: string;
  target: string;
  sourceName: string;
  targetName: string;
  bidirectional: boolean;
  activityOnly: boolean;
  roleForward?: string;
  roleReverse?: string;
}

interface MessageTarget {
  msg: TeamChatMessage;
  sourceId: string;
  targetId: string;
  sourceName: string;
  targetName: string;
}

interface TeamMapData {
  nodes: Node<TeamNodeData>[];
  edges: Edge<TeamEdgeData>[];
  nodeSummaries: Record<string, TeamNodeData>;
  edgeSummaries: Record<string, TeamEdgeData>;
}

const EMPTY_TEAM_MESSAGES: TeamChatMessage[] = [];
const EMPTY_TEAM_MEMBERS: SingleAgent[] = [];
const EMPTY_TEAM_CONTACTS: Record<string, Record<string, string>> = {};

const NODE_COLORS = [
  "#0066cc",
  "#34c759",
  "#ff9500",
  "#8b5cf6",
  "#06b6d4",
  "#ff3b30",
  "#a855f7",
  "#84cc16",
  "#ec4899",
  "#14b8a6",
];

const STATE_LABEL: Record<AgentState, string> = {
  ready: "Ready",
  running: "Running",
  waiting: "Waiting",
  error: "Error",
};

const STATE_COLOR: Record<AgentState, string> = {
  ready: "var(--color-ink-4)",
  running: "var(--color-success)",
  waiting: "var(--color-success)",
  error: "var(--color-danger)",
};

const STATE_BG: Record<AgentState, string> = {
  ready: "#f5f5f7",
  running: "#f0fdf4",
  waiting: "#f0fdf4",
  error: "#fff1f0",
};

const MODE_META: Record<ViewMode, { label: string; icon: typeof GitBranch }> = {
  structure: { label: "Structure", icon: GitBranch },
  activity: { label: "Activity", icon: Activity },
  replay: { label: "Replay", icon: History },
  list: { label: "List", icon: List },
};

const FOCUS_COLOR: Record<Exclude<RelationFocus, null>, string> = {
  incoming: "#ff9500",
  outgoing: "#0066cc",
  bidirectional: "#8b5cf6",
};

const NODE_WIDTH = 96;
const NODE_HEIGHT = 92;
const AVATAR_SIZE = 58;
const MSG_PAGE_SIZE = 30;

function getNodeColor(index: number): string {
  return NODE_COLORS[index % NODE_COLORS.length];
}

function getState(state?: string): AgentState {
  if (state === "running" || state === "waiting" || state === "error") {
    return state;
  }
  return "ready";
}

function formatTime(ts?: number) {
  if (!ts) return "No activity";
  return new Date(ts * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function truncate(value: string, max = 88) {
  return value.length > max ? `${value.slice(0, max - 1)}...` : value;
}

function pairKey(a: string, b: string) {
  return [a, b].sort().join("<>");
}

function relationId(source: string, target: string, bidirectional = false) {
  return bidirectional
    ? `relation-${pairKey(source, target)}`
    : `relation-${source}->${target}`;
}

function anchorPositionForAngle(angle: number): Position {
  const x = Math.cos(angle);
  const y = Math.sin(angle);
  if (Math.abs(x) >= Math.abs(y)) {
    return x >= 0 ? Position.Left : Position.Right;
  }
  return y >= 0 ? Position.Top : Position.Bottom;
}

function innerAnchorOffsetForAngle(angle: number) {
  const radius = AVATAR_SIZE / 2;
  return {
    x: NODE_WIDTH / 2 - Math.cos(angle) * radius,
    y: radius - Math.sin(angle) * radius,
  };
}

function getMessageTargets(
  messages: TeamChatMessage[],
  nameToId: Map<string, string>,
  memberNames: Set<string>,
): MessageTarget[] {
  const targets: MessageTarget[] = [];

  for (const msg of messages) {
    const sourceId = nameToId.get(msg.fromAgent);
    if (!sourceId) continue;

    const targetNames =
      msg.type === "broadcast"
        ? (() => {
            const explicitTargets = msg.toAgent
              .split(",")
              .map((name) => name.trim())
              .filter((name) => memberNames.has(name));
            return explicitTargets.length > 0
              ? explicitTargets
              : Array.from(memberNames).filter((name) => name !== msg.fromAgent);
          })()
        : memberNames.has(msg.toAgent)
          ? [msg.toAgent]
          : [];

    for (const targetName of targetNames) {
      if (targetName === msg.fromAgent) continue;
      const targetId = nameToId.get(targetName);
      if (!targetId) continue;
      targets.push({
        msg,
        sourceId,
        targetId,
        sourceName: msg.fromAgent,
        targetName,
      });
    }
  }

  return targets;
}

function buildRelations(
  members: SingleAgent[],
  contacts: Record<string, Record<string, string>>,
  messageTargets: MessageTarget[],
) {
  const nameToId = new Map(members.map((member) => [member.name, member.id]));
  const pairRelations = new Map<string, TeamRelation>();

  for (const [sourceName, sourceContacts] of Object.entries(contacts)) {
    const sourceId = nameToId.get(sourceName);
    if (!sourceId) continue;

    for (const [targetName, role] of Object.entries(sourceContacts || {})) {
      const targetId = nameToId.get(targetName);
      if (!targetId || targetId === sourceId) continue;
      const key = pairKey(sourceId, targetId);
      const existing = pairRelations.get(key);

      if (!existing) {
        pairRelations.set(key, {
          id: relationId(sourceId, targetId),
          source: sourceId,
          target: targetId,
          sourceName,
          targetName,
          bidirectional: false,
          activityOnly: false,
          roleForward: role,
        });
      } else {
        existing.bidirectional = true;
        existing.id = relationId(existing.source, existing.target, true);
        if (existing.source === sourceId && existing.target === targetId) {
          existing.roleForward = role;
        } else {
          existing.roleReverse = role;
        }
      }
    }
  }

  for (const target of messageTargets) {
    const key = pairKey(target.sourceId, target.targetId);
    if (pairRelations.has(key)) continue;
    pairRelations.set(key, {
      id: relationId(target.sourceId, target.targetId),
      source: target.sourceId,
      target: target.targetId,
      sourceName: target.sourceName,
      targetName: target.targetName,
      bidirectional: false,
      activityOnly: true,
    });
  }

  return Array.from(pairRelations.values());
}

function buildLayout(
  members: SingleAgent[],
  width: number,
  height: number,
) {
  const layout = new Map<string, { x: number; y: number; angle: number; anchorPosition: Position; anchorOffset: { x: number; y: number } }>();
  const cx = Math.max(width / 2 - NODE_WIDTH / 2, 80);
  const cy = Math.max(height / 2 - NODE_HEIGHT / 2, 80);
  const availableRadius = Math.max(
    128,
    Math.min(
      (width - NODE_WIDTH) / 2 - 16,
      (height - NODE_HEIGHT) / 2 - 16,
    ),
  );
  const desiredRadius = Math.max(
    168,
    Math.min(width, height) * 0.43,
    members.length * 24,
  );
  const radius = Math.min(desiredRadius, availableRadius);

  members.forEach((member, index) => {
    const angle = (Math.PI * 2 * index) / Math.max(members.length, 1) - Math.PI / 2;
    layout.set(member.id, {
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      angle,
      anchorPosition: anchorPositionForAngle(angle),
      anchorOffset: innerAnchorOffsetForAngle(angle),
    });
  });
  return layout;
}

function buildTeamMapData({
  members,
  contacts,
  messages,
  agentStates,
  dimensions,
  mode,
  selection,
  currentReplayMessage,
}: {
  members: SingleAgent[];
  contacts: Record<string, Record<string, string>>;
  messages: TeamChatMessage[];
  agentStates: Record<string, string>;
  dimensions: { width: number; height: number };
  mode: ViewMode;
  selection: Selection;
  currentReplayMessage?: TeamChatMessage;
}): TeamMapData {
  const nameToId = new Map(members.map((member) => [member.name, member.id]));
  const memberNames = new Set(members.map((member) => member.name));
  const messageTargets = getMessageTargets(messages, nameToId, memberNames);
  const currentTargets = currentReplayMessage
    ? getMessageTargets([currentReplayMessage], nameToId, memberNames)
    : [];
  const currentPairKeys = new Set(
    currentTargets.map((target) => pairKey(target.sourceId, target.targetId)),
  );

  const relations = buildRelations(members, contacts, messageTargets);
  const layout = buildLayout(members, dimensions.width, dimensions.height);

  const contactOut = new Map<string, number>();
  const contactIn = new Map<string, number>();
  const sent = new Map<string, number>();
  const received = new Map<string, number>();
  const latestNodeTs = new Map<string, number>();
  const pairMessages = new Map<string, RecentMessage[]>();
  const latestSourceByPair = new Map<string, string>();

  for (const [sourceName, sourceContacts] of Object.entries(contacts)) {
    const sourceId = nameToId.get(sourceName);
    if (!sourceId) continue;
    for (const targetName of Object.keys(sourceContacts || {})) {
      const targetId = nameToId.get(targetName);
      if (!targetId) continue;
      contactOut.set(sourceId, (contactOut.get(sourceId) || 0) + 1);
      contactIn.set(targetId, (contactIn.get(targetId) || 0) + 1);
    }
  }

  for (const target of messageTargets) {
    const key = pairKey(target.sourceId, target.targetId);
    const recent: RecentMessage = {
      fromAgent: target.msg.fromAgent,
      toAgent: target.msg.toAgent,
      content: target.msg.content,
      type: target.msg.type,
      timestamp: target.msg.timestamp,
    };
    const list = pairMessages.get(key) || [];
    list.push(recent);
    pairMessages.set(key, list);
    latestSourceByPair.set(key, target.sourceId);
    sent.set(target.sourceId, (sent.get(target.sourceId) || 0) + 1);
    received.set(target.targetId, (received.get(target.targetId) || 0) + 1);
    latestNodeTs.set(
      target.sourceId,
      Math.max(latestNodeTs.get(target.sourceId) || 0, target.msg.timestamp),
    );
    latestNodeTs.set(
      target.targetId,
      Math.max(latestNodeTs.get(target.targetId) || 0, target.msg.timestamp),
    );
  }

  for (const list of pairMessages.values()) {
    list.sort((a, b) => b.timestamp - a.timestamp);
  }

  const selectedNodeId = selection?.type === "node" ? selection.id : null;
  const selectedEdgeId = selection?.type === "edge" ? selection.id : null;
  const selectedEdge = selectedEdgeId
    ? relations.find((relation) => relation.id === selectedEdgeId)
    : undefined;
  const relatedNodeIds = new Set<string>();
  if (selectedNodeId) {
    for (const relation of relations) {
      if (relation.source === selectedNodeId || relation.target === selectedNodeId) {
        relatedNodeIds.add(relation.source);
        relatedNodeIds.add(relation.target);
      }
    }
  }
  if (selectedEdge) {
    relatedNodeIds.add(selectedEdge.source);
    relatedNodeIds.add(selectedEdge.target);
  }

  const colorById = new Map<string, string>();
  members.forEach((member, index) => colorById.set(member.id, getNodeColor(index)));

  const nodeSummaries: Record<string, TeamNodeData> = {};
  const anchorById = new Map<string, { x: number; y: number }>();
  const nodes: Node<TeamNodeData>[] = members.map((member, index) => {
    const layoutPosition = layout.get(member.id);
    const position = layoutPosition
      ? { x: layoutPosition.x, y: layoutPosition.y }
      : { x: 0, y: 0 };
    const anchorOffset = layoutPosition?.anchorOffset || {
      x: NODE_WIDTH / 2,
      y: AVATAR_SIZE,
    };
    anchorById.set(member.id, {
      x: position.x + anchorOffset.x,
      y: position.y + anchorOffset.y,
    });
    const selected = selectedNodeId === member.id;
    const dimmed =
      !!selection &&
      !selected &&
      !relatedNodeIds.has(member.id);
    const data: TeamNodeData = {
      label: member.name,
      state: getState(agentStates[member.id] || member.state),
      color: colorById.get(member.id) || getNodeColor(index),
      anchorPosition: layoutPosition?.anchorPosition || Position.Bottom,
      anchorOffset,
      contactOutCount: contactOut.get(member.id) || 0,
      contactInCount: contactIn.get(member.id) || 0,
      sentCount: sent.get(member.id) || 0,
      receivedCount: received.get(member.id) || 0,
      latestTs: latestNodeTs.get(member.id),
      selected,
      dimmed,
    };
    nodeSummaries[member.id] = data;
    return {
      id: member.id,
      type: "teamAgentNode",
      data,
      position,
      sourcePosition: data.anchorPosition,
      targetPosition: data.anchorPosition,
    };
  });

  const maxMessages = Math.max(
    1,
    ...Array.from(pairMessages.values()).map((list) => list.length),
  );

  const edgeSummaries: Record<string, TeamEdgeData> = {};
  const edges: Edge<TeamEdgeData>[] = relations.map((relation) => {
    const key = pairKey(relation.source, relation.target);
    const recentMessages = pairMessages.get(key) || [];
    const messageCount = recentMessages.length;
    const latestMessage = recentMessages[0];
    const active = currentPairKeys.has(key);
    const latestSourceColor =
      colorById.get(latestSourceByPair.get(key) || relation.source) || "#0066cc";
    const isStructure = mode === "structure";
    const hasActivity = messageCount > 0;
    const selected = selectedEdgeId === relation.id;
    const dimmed =
      !!selection &&
      !selected &&
      !(selectedNodeId && (relation.source === selectedNodeId || relation.target === selectedNodeId));
    const relationFocus: RelationFocus =
      selectedNodeId && relation.source === selectedNodeId && relation.target === selectedNodeId
        ? "bidirectional"
        : selectedNodeId && relation.bidirectional && (relation.source === selectedNodeId || relation.target === selectedNodeId)
          ? "bidirectional"
          : selectedNodeId && relation.source === selectedNodeId
            ? "outgoing"
            : selectedNodeId && relation.target === selectedNodeId
              ? "incoming"
              : null;

    const roleLabel =
      relation.roleForward && relation.roleReverse
        ? relation.roleForward === relation.roleReverse
          ? relation.roleForward
          : `${relation.roleForward} / ${relation.roleReverse}`
        : relation.roleForward || relation.roleReverse || "message";

    const label =
      mode === "activity"
        ? hasActivity
          ? `${messageCount}`
          : roleLabel
        : mode === "replay"
          ? active
            ? "now"
            : hasActivity
              ? `${messageCount}`
              : roleLabel
          : roleLabel;

    const activityIntensity = messageCount / maxMessages;
    const thickness = isStructure
      ? selected || relationFocus
        ? 2.8
        : 1.45
      : hasActivity
        ? 1.8 + activityIntensity * 1.8
        : 1.05;

    const color = isStructure
      ? relationFocus
        ? FOCUS_COLOR[relationFocus]
        : relation.activityOnly
          ? "#94a3b8"
          : "#9aa3af"
      : hasActivity
        ? latestSourceColor
        : "#cbd5e1";

    const data: TeamEdgeData = {
      mode,
      color,
      label,
      roleForward: relation.roleForward,
      roleReverse: relation.roleReverse,
      sourceName: relation.sourceName,
      targetName: relation.targetName,
      bidirectional: relation.bidirectional,
      activityOnly: relation.activityOnly,
      messageCount,
      latestTs: latestMessage?.timestamp,
      latestMessage,
      recentMessages,
      sourceAnchor: anchorById.get(relation.source) || { x: 0, y: 0 },
      targetAnchor: anchorById.get(relation.target) || { x: 0, y: 0 },
      thickness,
      pulseCount: mode === "activity" && hasActivity ? Math.min(4, Math.max(1, Math.ceil(activityIntensity * 4))) : 0,
      relationFocus,
      active,
      selected,
      dimmed,
    };
    edgeSummaries[relation.id] = data;

    return {
      id: relation.id,
      source: relation.source,
      target: relation.target,
      sourceHandle: "table-source",
      targetHandle: "table-target",
      type: "teamContactEdge",
      data,
      zIndex: selected || relationFocus || active ? 20 : 0,
      markerStart: relation.bidirectional
        ? {
            type: MarkerType.ArrowClosed,
            color,
            width: 12,
            height: 12,
          }
        : undefined,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color,
        width: 12,
        height: 12,
      },
      style: {
        opacity: dimmed ? 0.18 : 1,
      },
    };
  });

  return { nodes, edges, nodeSummaries, edgeSummaries };
}

function TeamAgentNode({ data }: { data: TeamNodeData }) {
  const statusColor = STATE_COLOR[data.state];
  const initials = data.label.slice(0, 2).toUpperCase();
  const activityCount = data.sentCount + data.receivedCount;

  return (
    <div
      className={cn(
        "relative w-[96px] h-[92px] flex flex-col items-center transition-all duration-200",
        data.dimmed && "opacity-35",
      )}
    >
      <Handle
        type="target"
        id="table-target"
        position={data.anchorPosition}
        className="!w-2 !h-2 !border-0 !bg-transparent"
        style={{
          left: data.anchorOffset.x,
          top: data.anchorOffset.y,
          transform: "translate(-50%, -50%)",
        }}
      />
      <Handle
        type="source"
        id="table-source"
        position={data.anchorPosition}
        className="!w-2 !h-2 !border-0 !bg-transparent"
        style={{
          left: data.anchorOffset.x,
          top: data.anchorOffset.y,
          transform: "translate(-50%, -50%)",
        }}
      />

      <div
        className={cn(
          "relative w-[58px] h-[58px] rounded-full flex items-center justify-center text-[14px] font-semibold text-white shadow-sm border-[3px] border-white transition-all duration-200",
          data.selected && "shadow-md ring-4 ring-(--color-primary)/20",
        )}
        style={{ backgroundColor: data.color }}
      >
        {initials}
        <span
          className={cn(
            "absolute right-[2px] top-[2px] w-3 h-3 rounded-full border-2 border-white",
            data.state === "running" && "animate-halo-green-yellow",
          )}
          style={{ backgroundColor: statusColor }}
          title={STATE_LABEL[data.state]}
        />
        {activityCount > 0 && (
          <span className="absolute -bottom-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-white border border-(--color-rule-soft) text-[9px] font-semibold text-slate-600 shadow-sm flex items-center justify-center tabular-nums">
            {activityCount > 99 ? "99+" : activityCount}
          </span>
        )}
      </div>
      <span
        className={cn(
          "absolute w-2 h-2 rounded-full border-2 border-white bg-slate-400 shadow-sm pointer-events-none",
          data.selected && "bg-(--color-primary)",
        )}
        style={{
          left: data.anchorOffset.x,
          top: data.anchorOffset.y,
          transform: "translate(-50%, -50%)",
        }}
      />
      <div
        className={cn(
          "mt-2 max-w-[92px] rounded-full border bg-white px-2 py-0.5 text-center text-[11px] font-semibold text-slate-700 shadow-sm truncate",
          data.selected && "border-(--color-primary) text-(--color-primary)",
        )}
        title={data.label}
      >
        {data.label}
      </div>
    </div>
  );
}

function TeamContactEdge({
  id,
  data,
  markerStart,
  markerEnd,
}: EdgeProps<Edge<TeamEdgeData>>) {
  if (!data) return null;
  const sourceX = data.sourceAnchor.x;
  const sourceY = data.sourceAnchor.y;
  const targetX = data.targetAnchor.x;
  const targetY = data.targetAnchor.y;
  const edgePath = `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`;
  const labelX = (sourceX + targetX) / 2;
  const labelY = (sourceY + targetY) / 2;
  const opacity = data.dimmed
    ? 0.18
    : data.mode === "structure"
      ? data.activityOnly
        ? 0.45
        : 0.78
      : data.messageCount > 0
        ? 0.72
        : 0.25;
  const dash = data.activityOnly || (data.mode !== "structure" && data.messageCount === 0)
    ? "5 5"
    : undefined;
  const showLabel = !!data.relationFocus;

  return (
    <>
      <g>
        {(data.active || data.selected || data.relationFocus) && (
          <path
            d={edgePath}
            fill="none"
            stroke={data.color}
            strokeWidth={data.thickness + (data.mode === "activity" ? 12 : 7)}
            strokeOpacity={data.active ? 0.24 : data.relationFocus ? 0.18 : 0.14}
            style={{ animation: data.active ? "team-edge-glow 1.4s ease-out infinite" : undefined }}
          />
        )}
        {data.mode === "activity" && data.messageCount > 0 && !data.dimmed && (
          <path
            d={edgePath}
            fill="none"
            stroke={data.color}
            strokeWidth={Math.max(6, data.thickness + 5)}
            strokeOpacity={0.12}
            strokeLinecap="round"
          />
        )}
        <path
          id={id}
          d={edgePath}
          fill="none"
          stroke={data.color}
          strokeWidth={data.thickness}
          strokeOpacity={opacity}
          strokeDasharray={dash}
          markerStart={markerStart}
          markerEnd={markerEnd}
          style={{ transition: "stroke-width 180ms ease, stroke-opacity 180ms ease" }}
        />
        {data.mode === "activity" && data.messageCount > 0 && !data.dimmed &&
          Array.from({ length: data.pulseCount }).map((_, index) => (
            <circle
              key={index}
              r={data.active ? 4.5 : 3.4}
              fill={data.color}
              opacity={data.active ? 0.95 : 0.72}
            >
              <animateMotion
                dur={`${Math.max(1.1, 2.6 - data.pulseCount * 0.24)}s`}
                begin={`${index * 0.32}s`}
                repeatCount="indefinite"
                path={edgePath}
              />
            </circle>
          ))}
        {data.mode === "replay" && data.active && (
          <circle r="4.5" fill={data.color}>
            <animateMotion dur="0.9s" repeatCount="indefinite" path={edgePath} />
          </circle>
        )}
      </g>
      {showLabel && data.label && !data.dimmed && (
        <EdgeLabelRenderer>
          <div
            className={cn(
              "nodrag nopan pointer-events-none absolute rounded bg-white px-1.5 py-0.5 text-[9px] font-semibold text-slate-600 border max-w-[128px] truncate",
              "shadow-md ring-2 ring-white",
            )}
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              color: data.mode === "structure" ? "#475569" : data.color,
              borderColor: data.color,
              zIndex: 80,
            }}
          >
            {data.mode === "activity" && data.messageCount > 0 ? `${data.messageCount} msg` : data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const nodeTypes = { teamAgentNode: TeamAgentNode };
const edgeTypes = { teamContactEdge: TeamContactEdge };

export function TeamGraphView({ width }: { width: number }) {
  const activeAgent = useAppStore((s) => {
    const agent = s.activeAgentId ? s.agents.find((item) => item.id === s.activeAgentId) : null;
    return agent && isTeam(agent) ? agent : null;
  });
  const activeAgentId = activeAgent?.id || "";
  const members = activeAgent?.members || EMPTY_TEAM_MEMBERS;
  const contacts = activeAgent?.contacts || EMPTY_TEAM_CONTACTS;
  const agentStates = useAppStore(useShallow((s) => {
    const states: Record<string, string> = {};
    for (const member of members) {
      states[member.id] = s.agentStates[member.id] || member.state;
    }
    return states;
  }));
  const closeTeamGraph = useAppStore((s) => s.closeTeamGraph);
  const messages = useAppStore((s) =>
    activeAgentId ? s.teamMessages[activeAgentId] || EMPTY_TEAM_MESSAGES : EMPTY_TEAM_MESSAGES
  );
  const scrollToTeamMessage = useAppStore((s) => s.scrollToTeamMessage);

  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({
    width: Math.max(width, 320),
    height: 420,
  });
  const [mode, setMode] = useState<ViewMode>("structure");
  const [selection, setSelection] = useState<Selection>(null);
  const [replayIndex, setReplayIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());
  const [expandedContacts, setExpandedContacts] = useState<Set<string>>(new Set());
  const [msgLoadCounts, setMsgLoadCounts] = useState<Record<string, number>>({});

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

  useEffect(() => {
    if (mode !== "replay") return;
    if (!isPlaying) return;
    const timer = window.setInterval(() => {
      setReplayIndex((current) => {
        if (messages.length === 0) return 0;
        if (current >= messages.length) return 1;
        return current + 1;
      });
    }, 1100);
    return () => window.clearInterval(timer);
  }, [mode, isPlaying, messages.length]);

  const effectiveReplayIndex = Math.min(replayIndex, messages.length);
  const visibleMessages = useMemo(
    () =>
      mode === "replay"
        ? messages.slice(0, effectiveReplayIndex)
        : messages,
    [mode, messages, effectiveReplayIndex],
  );
  const currentReplayMessage =
    mode === "replay" && effectiveReplayIndex > 0
      ? messages[effectiveReplayIndex - 1]
      : undefined;

  const mapData = useMemo(() => {
    if (members.length === 0) {
      return { nodes: [], edges: [], nodeSummaries: {}, edgeSummaries: {} };
    }
    return buildTeamMapData({
      members,
      contacts,
      messages: visibleMessages,
      agentStates,
      dimensions,
      mode,
      selection,
      currentReplayMessage,
    });
  }, [
    members,
    contacts,
    visibleMessages,
    agentStates,
    dimensions,
    mode,
    selection,
    currentReplayMessage,
  ]);

  const selectedNode =
    selection?.type === "node" ? mapData.nodeSummaries[selection.id] : undefined;
  const selectedEdge =
    selection?.type === "edge" ? mapData.edgeSummaries[selection.id] : undefined;

  const contactCount = useMemo(() => {
    return Object.values(contacts).reduce(
      (sum, contactMap) => sum + Object.keys(contactMap || {}).length,
      0,
    );
  }, [contacts]);

  const handleNodeClick = useCallback((_event: React.MouseEvent, node: Node) => {
    setSelection({ type: "node", id: node.id });
  }, []);

  const handleEdgeClick = useCallback((_event: React.MouseEvent, edge: Edge) => {
    setSelection({ type: "edge", id: edge.id });
  }, []);

  const handlePaneClick = useCallback(() => {
    setSelection(null);
  }, []);

  const jumpToMessage = useCallback(
    (msg: RecentMessage) => {
      scrollToTeamMessage({
        timestamp: msg.timestamp,
        fromAgent: msg.fromAgent,
        toAgent: msg.toAgent,
      });
    },
    [scrollToTeamMessage],
  );

  const stepReplay = useCallback(
    (direction: -1 | 1) => {
      setIsPlaying(false);
      setReplayIndex((current) => {
        const next = current + direction;
        return Math.max(0, Math.min(messages.length, next));
      });
    },
    [messages.length],
  );

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

  const showEdgeInList = useCallback((edge: TeamEdgeData) => {
    const contactKey = `${edge.sourceName}|${edge.targetName}`;
    setMode("list");
    setIsPlaying(false);
    setSelection(null);
    setExpandedAgents((prev) => {
      const next = new Set(prev);
      next.add(edge.sourceName);
      if (edge.bidirectional) next.add(edge.targetName);
      return next;
    });
    setExpandedContacts((prev) => {
      const next = new Set(prev);
      next.add(contactKey);
      if (edge.bidirectional) next.add(`${edge.targetName}|${edge.sourceName}`);
      return next;
    });
    setMsgLoadCounts((prev) => ({
      ...prev,
      [contactKey]: Math.max(prev[contactKey] || 0, edge.messageCount),
      ...(edge.bidirectional
        ? {
            [`${edge.targetName}|${edge.sourceName}`]: Math.max(
              prev[`${edge.targetName}|${edge.sourceName}`] || 0,
              edge.messageCount,
            ),
          }
        : {}),
    }));
  }, []);

  if (!activeAgent || members.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-(--color-ink-3) text-sm">
        No team selected
      </div>
    );
  }

  return (
    <div className="h-full w-full flex flex-col bg-(--color-background)">
      <div className="shrink-0 border-b border-(--color-rule-soft)">
        <div className="flex items-center justify-between px-3 py-2 gap-2">
          <div className="flex items-center gap-1 rounded-md bg-(--color-secondary) p-0.5">
            {(Object.keys(MODE_META) as ViewMode[]).map((key) => {
              const Icon = MODE_META[key].icon;
              const active = mode === key;
              return (
                <button
                  key={key}
                  onClick={() => {
                    setMode(key);
                    setSelection(null);
                    if (key === "replay") {
                      setReplayIndex(messages.length);
                    } else {
                      setIsPlaying(false);
                    }
                  }}
                  className={cn(
                    "h-7 px-2 rounded flex items-center gap-1.5 text-[11px] font-medium transition-colors",
                    active
                      ? "bg-white text-(--color-foreground) shadow-sm"
                      : "text-(--color-ink-2) hover:text-(--color-foreground)",
                  )}
                  title={MODE_META[key].label}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {MODE_META[key].label}
                </button>
              );
            })}
          </div>
          <button
            onClick={closeTeamGraph}
            className="p-1 rounded hover:bg-(--color-secondary) text-(--color-ink-3) transition-colors"
            title="关闭"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-3 pb-2 flex items-center gap-3 text-[11px] text-(--color-ink-3)">
          <span className="flex items-center gap-1">
            <Users className="w-3.5 h-3.5" />
            {members.length} agents
          </span>
          <span className="flex items-center gap-1">
            <GitBranch className="w-3.5 h-3.5" />
            {contactCount} contacts
          </span>
          <span className="flex items-center gap-1">
            <MessageSquare className="w-3.5 h-3.5" />
            {visibleMessages.length} messages
          </span>
        </div>

        {mode === "replay" && (
          <div className="px-3 pb-2 flex items-center gap-2">
            <button
              onClick={() => stepReplay(-1)}
              disabled={effectiveReplayIndex <= 0}
              className="w-7 h-7 rounded flex items-center justify-center bg-(--color-secondary) hover:bg-(--color-secondary-hover) text-(--color-foreground) disabled:opacity-40 disabled:hover:bg-(--color-secondary)"
              title="Previous message"
            >
              <SkipBack className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setIsPlaying((value) => !value)}
              className="w-7 h-7 rounded flex items-center justify-center bg-(--color-secondary) hover:bg-(--color-secondary-hover) text-(--color-foreground)"
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <button
              onClick={() => stepReplay(1)}
              disabled={effectiveReplayIndex >= messages.length}
              className="w-7 h-7 rounded flex items-center justify-center bg-(--color-secondary) hover:bg-(--color-secondary-hover) text-(--color-foreground) disabled:opacity-40 disabled:hover:bg-(--color-secondary)"
              title="Next message"
            >
              <SkipForward className="w-3.5 h-3.5" />
            </button>
            <input
              type="range"
              min={0}
              max={messages.length}
              value={effectiveReplayIndex}
              onChange={(event) => {
                setReplayIndex(Number(event.target.value));
                setIsPlaying(false);
              }}
              className="min-w-0 flex-1 accent-(--color-primary)"
            />
            <span className="w-14 text-right text-[10px] tabular-nums text-(--color-ink-3)">
              {effectiveReplayIndex}/{messages.length}
            </span>
          </div>
        )}
      </div>

      <div className="flex-1 min-h-0 flex flex-col">
        {(selectedNode || selectedEdge || mode === "replay") && (
          <TeamInspector
            mode={mode}
            selectedNode={selectedNode}
            selectedEdge={selectedEdge}
            currentReplayMessage={currentReplayMessage}
            onJumpToMessage={jumpToMessage}
            onShowInList={showEdgeInList}
          />
        )}
        {mode === "list" ? (
          <ListView
            members={members}
            contacts={contacts}
            agentStates={agentStates}
            messages={messages}
            expandedAgents={expandedAgents}
            expandedContacts={expandedContacts}
            msgLoadCounts={msgLoadCounts}
            onToggleAgent={toggleAgentExpand}
            onToggleContact={toggleContactExpand}
            onLoadMore={loadMoreMessages}
            onJumpToMessage={jumpToMessage}
          />
        ) : (
          <div className="flex-1 min-h-0" ref={containerRef}>
            <ReactFlow
              nodes={mapData.nodes}
              edges={mapData.edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onNodeClick={handleNodeClick}
              onEdgeClick={handleEdgeClick}
              onPaneClick={handlePaneClick}
              fitView
              fitViewOptions={{ padding: 0.24 }}
              proOptions={{ hideAttribution: true }}
              minZoom={0.25}
              maxZoom={1.8}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable
              className="bg-(--color-background)"
            >
              <Background color="#ececef" gap={20} size={1} />
              <Controls showInteractive={false} className="!border-slate-200 !shadow-sm" />
            </ReactFlow>
          </div>
        )}
      </div>

      <style>{`
        @keyframes team-edge-glow {
          0%, 100% { stroke-opacity: 0.16; }
          50% { stroke-opacity: 0.32; }
        }
      `}</style>
    </div>
  );
}

function TeamInspector({
  mode,
  selectedNode,
  selectedEdge,
  currentReplayMessage,
  onJumpToMessage,
  onShowInList,
}: {
  mode: ViewMode;
  selectedNode?: TeamNodeData;
  selectedEdge?: TeamEdgeData;
  currentReplayMessage?: TeamChatMessage;
  onJumpToMessage: (msg: RecentMessage) => void;
  onShowInList: (edge: TeamEdgeData) => void;
}) {
  if (selectedNode) {
    return (
      <div className="shrink-0 border-b border-(--color-rule-soft) bg-white px-3 py-2">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="text-[12px] font-semibold text-slate-800 truncate">
              {selectedNode.label}
            </div>
            <div className="text-[10px] text-(--color-ink-3) mt-0.5">
              Last activity: {formatTime(selectedNode.latestTs)}
            </div>
          </div>
          <span
            className={cn(
              "text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0",
              selectedNode.state === "running" && "animate-halo-green-yellow",
            )}
            style={{
              color: STATE_COLOR[selectedNode.state],
              backgroundColor: STATE_BG[selectedNode.state],
            }}
          >
            {STATE_LABEL[selectedNode.state]}
          </span>
        </div>
        <div className="grid grid-cols-4 gap-1.5 mt-2">
          <StatPill label="Out" value={selectedNode.contactOutCount} />
          <StatPill label="In" value={selectedNode.contactInCount} />
          <StatPill label="Sent" value={selectedNode.sentCount} />
          <StatPill label="Recv" value={selectedNode.receivedCount} />
        </div>
        {mode === "structure" && (
          <div className="mt-2 flex items-center gap-3 text-[10px] text-(--color-ink-3)">
            <LegendDot color={FOCUS_COLOR.outgoing} label="Out" />
            <LegendDot color={FOCUS_COLOR.incoming} label="In" />
            <LegendDot color={FOCUS_COLOR.bidirectional} label="Both" />
          </div>
        )}
      </div>
    );
  }

  if (selectedEdge) {
    return (
      <div className="shrink-0 border-b border-(--color-rule-soft) bg-white px-3 py-2 max-h-[220px] overflow-y-auto">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[12px] font-semibold text-slate-800 truncate">
              {selectedEdge.sourceName}
              {selectedEdge.bidirectional ? " ↔ " : " → "}
              {selectedEdge.targetName}
            </div>
            <div className="text-[10px] text-(--color-ink-3) mt-0.5 truncate">
              {selectedEdge.roleForward || selectedEdge.roleReverse || "Activity-only relation"}
              {selectedEdge.roleReverse && selectedEdge.roleForward !== selectedEdge.roleReverse
                ? ` / ${selectedEdge.roleReverse}`
                : ""}
            </div>
          </div>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-(--color-secondary) text-(--color-ink-2) shrink-0">
            {selectedEdge.messageCount} msgs
          </span>
        </div>
        <div className="mt-2 space-y-1.5">
          {selectedEdge.recentMessages.length === 0 ? (
            <div className="text-[10px] text-(--color-ink-3)">No messages yet</div>
          ) : (
            selectedEdge.recentMessages.slice(0, 5).map((msg, index) => (
              <button
                key={`${msg.timestamp}-${index}`}
                onClick={() => onJumpToMessage(msg)}
                className="w-full text-left rounded border border-(--color-rule-soft) px-2 py-1.5 hover:bg-blue-50/60 transition-colors"
              >
                <div className="flex items-center gap-1.5 text-[10px] text-(--color-ink-3)">
                  {msg.type === "broadcast" ? (
                    <Radio className="w-3 h-3 text-amber-500" />
                  ) : (
                    <MessageSquare className="w-3 h-3 text-(--color-primary)" />
                  )}
                  <span className="font-medium text-slate-600">
                    {msg.fromAgent} → {msg.type === "broadcast" ? "broadcast" : msg.toAgent}
                  </span>
                  <span className="ml-auto tabular-nums">{formatTime(msg.timestamp)}</span>
                </div>
                <div className="text-[11px] text-slate-600 truncate mt-0.5">
                  {truncate(msg.content, 72)}
                </div>
              </button>
            ))
          )}
          {selectedEdge.recentMessages.length > 5 && (
            <button
              onClick={() => onShowInList(selectedEdge)}
              className="w-full flex items-center justify-center gap-1.5 rounded border border-(--color-rule-soft) px-2 py-1.5 text-[11px] font-medium text-(--color-primary) hover:bg-blue-50/60 transition-colors"
            >
              <List className="w-3.5 h-3.5" />
              More in List
            </button>
          )}
        </div>
      </div>
    );
  }

  if (mode === "replay") {
    return (
      <div className="shrink-0 border-b border-(--color-rule-soft) bg-white px-3 py-2">
        {currentReplayMessage ? (
          <button
            onClick={() =>
              onJumpToMessage({
                fromAgent: currentReplayMessage.fromAgent,
                toAgent: currentReplayMessage.toAgent,
                content: currentReplayMessage.content,
                type: currentReplayMessage.type,
                timestamp: currentReplayMessage.timestamp,
              })
            }
            className="w-full text-left"
          >
            <div className="flex items-center gap-1.5 text-[10px] text-(--color-ink-3)">
              {currentReplayMessage.type === "broadcast" ? (
                <Radio className="w-3 h-3 text-amber-500" />
              ) : (
                <MessageSquare className="w-3 h-3 text-(--color-primary)" />
              )}
              <span className="font-medium text-slate-600">
                {currentReplayMessage.fromAgent} →{" "}
                {currentReplayMessage.type === "broadcast"
                  ? "broadcast"
                  : currentReplayMessage.toAgent}
              </span>
              <span className="ml-auto tabular-nums">
                {formatTime(currentReplayMessage.timestamp)}
              </span>
            </div>
            <div className="text-[11px] text-slate-600 truncate mt-1">
              {truncate(currentReplayMessage.content, 96)}
            </div>
          </button>
        ) : (
          <div className="text-[11px] text-(--color-ink-3)">Replay is at the start</div>
        )}
      </div>
    );
  }

  return null;
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded bg-(--color-secondary) px-2 py-1.5 text-center">
      <div className="text-[12px] font-semibold tabular-nums text-slate-800">
        {value}
      </div>
      <div className="text-[9px] text-(--color-ink-3)">{label}</div>
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}

function ListView({
  members,
  contacts,
  agentStates,
  messages,
  expandedAgents,
  expandedContacts,
  msgLoadCounts,
  onToggleAgent,
  onToggleContact,
  onLoadMore,
  onJumpToMessage,
}: {
  members: SingleAgent[];
  contacts: Record<string, Record<string, string>>;
  agentStates: Record<string, string>;
  messages: TeamChatMessage[];
  expandedAgents: Set<string>;
  expandedContacts: Set<string>;
  msgLoadCounts: Record<string, number>;
  onToggleAgent: (name: string) => void;
  onToggleContact: (key: string) => void;
  onLoadMore: (key: string) => void;
  onJumpToMessage: (msg: RecentMessage) => void;
}) {
  const memberNames = useMemo(
    () => new Set(members.map((member) => member.name)),
    [members],
  );

  return (
    <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2 bg-(--color-background)">
      {members.map((member) => {
        const state = getState(agentStates[member.id] || member.state);
        const color = STATE_COLOR[state];
        const bg = STATE_BG[state];
        const isExpanded = expandedAgents.has(member.name);
        const agentContacts: Record<string, string> = {
          ...(contacts[member.name] || {}),
        };
        for (const msg of messages) {
          if (msg.fromAgent !== member.name) continue;
          if (msg.type === "broadcast") {
            const targets = msg.toAgent
              .split(",")
              .map((name) => name.trim())
              .filter((name) => memberNames.has(name) && name !== member.name);
            for (const target of targets) {
              if (!agentContacts[target]) agentContacts[target] = "broadcast activity";
            }
          } else if (memberNames.has(msg.toAgent) && !agentContacts[msg.toAgent]) {
            agentContacts[msg.toAgent] = "activity";
          }
        }

        return (
          <div
            key={member.id}
            className="rounded-md border border-(--color-rule-soft) bg-white overflow-hidden"
          >
            <button
              onClick={() => onToggleAgent(member.name)}
              className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left hover:bg-(--color-secondary) transition-colors"
            >
              <span
                className={cn(
                  "w-2.5 h-2.5 rounded-full shrink-0",
                  state === "running" && "animate-halo-green-yellow",
                )}
                style={{ backgroundColor: color }}
              />
              <span className="text-[12px] font-medium text-slate-800 flex-1 min-w-0 truncate">
                {member.name}
              </span>
              <span
                className="text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0"
                style={{ backgroundColor: bg, color }}
              >
                {STATE_LABEL[state]}
              </span>
              <ChevronDown
                className={cn(
                  "w-3.5 h-3.5 text-slate-400 transition-transform shrink-0",
                  isExpanded && "rotate-180",
                )}
              />
            </button>

            {isExpanded && (
              <div className="border-t border-(--color-rule-soft) bg-slate-50/50">
                {Object.keys(agentContacts).length === 0 ? (
                  <p className="text-[11px] text-slate-400 px-3 py-2">
                    No contacts
                  </p>
                ) : (
                  Object.entries(agentContacts).map(([contactName, role]) => {
                    const contactKey = `${member.name}|${contactName}`;
                    const isContactExpanded = expandedContacts.has(contactKey);
                    const contactMsgs = messages
                      .filter(
                        (msg) =>
                          msg.fromAgent === member.name &&
                          (msg.toAgent === contactName ||
                            (msg.type === "broadcast" &&
                              msg.toAgent
                                .split(",")
                                .map((name) => name.trim())
                                .includes(contactName))),
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
                        <button
                          onClick={() => onToggleContact(contactKey)}
                          className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-slate-100/70 transition-colors"
                        >
                          <span className="font-medium text-[11px] text-slate-600 w-20 shrink-0 truncate">
                            {contactName}
                          </span>
                          <span className="text-[11px] text-slate-400 truncate flex-1">
                            {role || "-"}
                          </span>
                          <span className="text-[10px] text-slate-300 tabular-nums shrink-0">
                            {contactMsgs.length}
                          </span>
                          <ChevronDown
                            className={cn(
                              "w-3 h-3 text-slate-400 transition-transform shrink-0",
                              isContactExpanded && "rotate-180",
                            )}
                          />
                        </button>

                        {isContactExpanded && (
                          <div className="border-t border-(--color-rule-soft) bg-white">
                            {visibleMsgs.length === 0 ? (
                              <p className="text-[10px] text-slate-400 px-3 py-2">
                                No messages yet
                              </p>
                            ) : (
                              visibleMsgs.map((msg, index) => {
                                const recent: RecentMessage = {
                                  fromAgent: msg.fromAgent,
                                  toAgent: msg.toAgent,
                                  content: msg.content,
                                  type: msg.type,
                                  timestamp: msg.timestamp,
                                };

                                return (
                                  <button
                                    key={`${msg.timestamp}-${index}`}
                                    onClick={() => onJumpToMessage(recent)}
                                    className="w-full flex items-start gap-2 px-3 py-1.5 text-left hover:bg-blue-50/60 transition-colors border-b border-(--color-rule-soft) last:border-b-0"
                                  >
                                    <span className="text-[10px] text-slate-400 tabular-nums shrink-0 mt-px">
                                      {formatTime(msg.timestamp)}
                                    </span>
                                    {msg.type === "broadcast" && (
                                      <span className="text-[9px] text-amber-500 font-semibold shrink-0 mt-px">
                                        [B]
                                      </span>
                                    )}
                                    <span className="text-[11px] text-slate-600 truncate flex-1 min-w-0">
                                      {truncate(msg.content, 64)}
                                    </span>
                                  </button>
                                );
                              })
                            )}
                            {hasMore && (
                              <button
                                onClick={() => onLoadMore(contactKey)}
                                className="w-full flex items-center justify-center py-1.5 hover:bg-slate-50 transition-colors"
                                title="Load more"
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
