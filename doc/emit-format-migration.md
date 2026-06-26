# Emit 格式统一迁移备忘录

## 已完成（bbagent 层）

- `bbagent/core/input.py`: `EventType` → `InputType`，`AgentEvent` → `InputEvent`，枚举值改为 `user_input` / `timer_input` / `agent_input`
- `bbagent/core/agent.py`: `_emit` 输出格式统一为 `{"type": "stream_chunk", "chunk_type": "..."}` 和 `{"type": "event", "event_type": "..."}` 两大类
- `bbagent/__init__.py` + `bbagent/core/__init__.py`: 导出名更新
- `tests/unit/core/`: 全部测试通过

---

## 待迁移（backend 层）

以下文件通过字符串匹配 chunk type，需改为新格式：

### `backend/dispatcher.py`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L20 | `chunk.get("type") != "completed_message"` | `chunk.get("type") != "stream_chunk" or chunk.get("chunk_type") != "completed_message"` |
| L31 | `chunk.get("type") == "agent_state" and chunk.get("state") == "error"` | `chunk.get("type") == "event" and chunk.get("event_type") == "agent_state" and chunk.get("state") == "error"` |
| L52 | comment: `completed_message` | 注释更新 |

### `backend/factories/agent_factory.py`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L649 | comment: `agent_state` | 注释更新 |
| L659 | `chunk.get("type") == "agent_state"` | `chunk.get("type") == "event" and chunk.get("event_type") == "agent_state"` |
| L663 | `chunk.get("type") == "agent_state"` | `chunk.get("type") == "event" and chunk.get("event_type") == "agent_state"` |
| L672 | `"type": "agent_state"` | `"type": "event", "event_type": "agent_state"` |

### `backend/api/chat.py`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L44 | comment: `agent_state` | 注释更新 |
| L89 | `"agent_state": agent.state` | `"type": "event", "event_type": "agent_state", "state": agent.state` |
| L120 | comment: `agent_state` | 注释更新 |
| L147 | `msg_type == "user_message"` | `msg_type == "user_input"` |

### `backend/schemas.py`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L232 | `Literal["user_message", "system_event"]` | `Literal["user_input", "timer_input", "agent_input", "system_event"]` |

### `backend/api/team_ws.py`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L46 | `msg_type != "user_message"` | `msg_type != "user_input"` |

### `backend/state.py`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L70 | comment: `agent_state` | 注释更新 |
| L291 | `get_agent_state` | 方法名不变，但内部逻辑需适配新事件格式 |
| L309 | `get_agent_messages` | 同上 |

---

## 待迁移（frontend 层）

### `frontend/src/components/ChatWindow.tsx`（核心消费者）
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L178 | `message.chunkType === "input_event"` | `message.type === "event" && message.event_type in ("user_input", "timer_input", "agent_input")` |
| L549 | comment: `input_event` | 注释更新 |
| L552 | `m.chunkType === "input_event"` | 同上 |
| L588 | comment: `agent_state` | 注释更新 |
| L646 | `chunk.type === "completed_tool_use"` | `chunk.type === "stream_chunk" && chunk.chunk_type === "completed_tool_use"` |
| L660 | `chunk.type === "tool_results"` | `chunk.type === "stream_chunk" && chunk.chunk_type === "tool_results"` |
| L735 | `chunk.type === "input_event"` | `chunk.type === "event" && chunk.event_type ...` |
| L738 | `eventType === "user_message"` | `eventType === "user_input"` |
| L747 | `chunkType: "input_event"` | `type: "event"` |
| L753 | `eventType === "timer_trigger"` | `eventType === "timer_input"` |
| L768 | `chunkType: "input_event"` | `type: "event"` |
| L771 | `chunk.type === "completed_message"` | `chunk.type === "stream_chunk" && chunk.chunk_type === "completed_message"` |
| L803 | `chunk.type === "interrupted"` | `chunk.type === "event" && chunk.event_type === "interrupted"` |
| L812 | `chunk.agent_state` | `chunk.state` |
| L895 | `{ type: "user_message"...}` | `{ type: "user_input"...}` |

### `frontend/src/types/index.ts`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L60 | `chunkType?: "text" \| "thinking" \| "tool_use" \| "tool_result" \| "todo_list" \| "error" \| "input_event"` | 改为 `type: "stream_chunk" \| "event"`，配合 `chunkType?: "text" \| "thinking" \| "completed_tool_use" \| "completed_message" \| "tool_results"` 和 `eventType?: "user_input" \| "timer_input" \| "agent_input" \| "interrupted" \| "agent_state" \| "error"` |

### `frontend/src/store/index.ts`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L161 | comment: `agent_state` | 注释更新 |

### `frontend/src/hooks/useGlobalAgentState.ts`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L9 | comment: `agent_state` | 注释更新 |
| L12 | comment: `user_message` | 注释更新 |
| L56-L57 | comment + `chunk.type === "agent_state"` | `chunk.type === "event" && chunk.event_type === "agent_state"` |

### `frontend/src/components/TeamChatWindow.tsx`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L216 | `type: "user_message"` | `type: "user_input"` |

### `frontend/src/App.tsx`
| 行号 | 旧代码 | 新代码 |
|---|---|---|
| L24 | comment: `agent_state` | 注释更新 |

---

## 待迁移（tests/unit/backend）

### `tests/unit/backend/test_dispatcher.py`
全部 chunk 构造需改为新格式（`"type": "completed_tool_use"` → `"type": "stream_chunk", "chunk_type": "completed_tool_use"` 等）
