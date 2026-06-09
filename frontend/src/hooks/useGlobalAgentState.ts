import { useEffect, useRef } from "react";
import { useAppStore } from "../store";
import { createChatWs } from "../lib/api";

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
  const reconnectDelayRef = useRef(1000);
  const MAX_RECONNECT_DELAY = 30000;

  useEffect(() => {
    let stopped = false;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout>;

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

    connect();

    return () => {
      stopped = true;
      clearTimeout(reconnectTimer);
      ws?.close();
      useAppStore.setState({ chatWs: null, onWsChunk: null });
    };
  }, [setAgentState, setAgentContextTokens]);
}
