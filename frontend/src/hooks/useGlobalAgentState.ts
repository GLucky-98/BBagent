import { useEffect, useRef } from "react";
import { useAppStore } from "../store";
import { createChatWs, createFileWatchWs } from "../lib/api";

/**
 * 唯一的 WebSocket 持有者。
 *
 * 挂载在 App 根级别，始终存活。处理两类消息：
 *   - agent_state → 直接更新 store.agentStates（全局状态指示灯）
 *   - 其他消息   → 委托给 store.onWsChunk（由 ChatWindow 注册）
 *
 * ChatWindow 通过 store.chatWs 发送消息（switch_agent、user_message 等）。
 */
export function useGlobalAgentState() {
  const setAgentState = useAppStore((s) => s.setAgentState);
  const setAgentContextTokens = useAppStore((s) => s.setAgentContextTokens);
  const refreshWorkingDir = useAppStore((s) => s.refreshWorkingDir);
  const refreshBaseDir = useAppStore((s) => s.refreshBaseDir);
  const reconnectDelayRef = useRef(1000);
  const fileWatchReconnectDelayRef = useRef(1000);
  const MAX_RECONNECT_DELAY = 30000;

  useEffect(() => {
    let stopped = false;
    let ws: WebSocket | null = null;
    let fileWatchWs: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;
    let fileWatchReconnectTimer: ReturnType<typeof setTimeout>;

    function sendFileWatchTarget() {
      if (stopped || fileWatchWs?.readyState !== WebSocket.OPEN) return;
      const id = useAppStore.getState().activeAgentId;
      fileWatchWs.send(JSON.stringify({
        type: "watch_files",
        agent_id: id,
      }));
    }

    function connect() {
      if (stopped) return;
      ws = createChatWs();
      useAppStore.setState({ chatWs: ws });

      ws.onopen = () => {
        reconnectDelayRef.current = 1000;
        const id = useAppStore.getState().activeAgentId;
        if (id) {
          ws!.send(JSON.stringify({ type: "switch_agent", agent_id: id }));
        }
      };

      ws.onmessage = (event) => {
        try {
          const chunk = JSON.parse(event.data);

          // agent_state 始终由 hook 处理，不走 ChatWindow 回调
          if (chunk.type === "agent_state") {
            setAgentState(
              chunk.agent_id || "",
              chunk.state as "ready" | "waiting" | "running" | "error",
            );
            if (typeof chunk.context_tokens === "number") {
              setAgentContextTokens(chunk.agent_id || "", chunk.context_tokens);
            }
            return;
          }

          // 其他所有消息委托给 ChatWindow 注册的回调
          const handler = useAppStore.getState().onWsChunk;
          if (handler) {
            handler(chunk);
          }
        } catch {
          // 忽略解析失败
        }
      };

      ws.onclose = () => {
        if (stopped) return;
        useAppStore.setState({ chatWs: null });
        reconnectTimer = setTimeout(() => {
          reconnectDelayRef.current = Math.min(
            reconnectDelayRef.current * 2,
            MAX_RECONNECT_DELAY,
          );
          connect();
        }, reconnectDelayRef.current);
      };
    }

    function connectFileWatch() {
      if (stopped) return;
      fileWatchWs = createFileWatchWs();

      fileWatchWs.onopen = () => {
        fileWatchReconnectDelayRef.current = 1000;
        sendFileWatchTarget();
      };

      fileWatchWs.onmessage = (event) => {
        try {
          const chunk = JSON.parse(event.data);
          if (chunk.type !== "file_tree_changed") return;

          const scopes = Array.isArray(chunk.scopes) ? chunk.scopes : [];
          if (scopes.includes("workingDir")) {
            refreshWorkingDir();
          }
          if (scopes.includes("baseDir")) {
            refreshBaseDir();
          }
          if (scopes.length === 0) {
            refreshWorkingDir();
            refreshBaseDir();
          }
        } catch {
          // 忽略解析失败
        }
      };

      fileWatchWs.onclose = () => {
        if (stopped) return;
        fileWatchReconnectTimer = setTimeout(() => {
          fileWatchReconnectDelayRef.current = Math.min(
            fileWatchReconnectDelayRef.current * 2,
            MAX_RECONNECT_DELAY,
          );
          connectFileWatch();
        }, fileWatchReconnectDelayRef.current);
      };
    }

    connect();
    connectFileWatch();

    const unsubscribe = useAppStore.subscribe((state, prevState) => {
      if (
        state.activeAgentId !== prevState.activeAgentId
        || state.workingDirPath !== prevState.workingDirPath
        || state.baseDirPath !== prevState.baseDirPath
      ) {
        sendFileWatchTarget();
      }
    });

    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      clearTimeout(fileWatchReconnectTimer);
      unsubscribe();
      ws?.close();
      fileWatchWs?.close();
      useAppStore.setState({ chatWs: null, onWsChunk: null });
    };
  }, [setAgentState, setAgentContextTokens, refreshWorkingDir, refreshBaseDir]);
}
