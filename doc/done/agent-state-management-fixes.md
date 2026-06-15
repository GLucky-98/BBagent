# Agent State 管理问题分析与修复方案

## 问题概述

Agent 的状态管理存在两个问题：

1. **finally 块强制覆盖 Error 状态**：流式循环和单次运行的 `finally` 块无条件将 state 重置为 `Ready`，导致错误状态被吞掉。
2. **_emit 硬编码字符串 vs AgentState 枚举值不一致**：emit 使用小写字符串 `'ready'`，AgentState 使用 Pascal 大小写 `'Ready'`，后端需要额外 `.lower()` 转换。

---

## 问题 1：finally 块强制覆盖 Error 状态

### 1.1 受影响的位置

#### 位置 A：`_stream_loop` finally 块 (`bbagent/core/agent.py#L610-617`)

```python
# 事件处理异常分支 (L593-609)
except Exception as e:
    self.logger.error(...)
    await self._emit({'type': 'agent_state', 'state': 'error'})
    self.state = AgentState.Error        # ← 设置为 Error

# while 循环结束后 (L610-611)
if self._loop_running:                   # ← 仅 break 退出时执行
    self.state = AgentState.Waiting

# finally 块 (L616-617)
finally:
    ...
    self.state = AgentState.Ready        # ← 无条件覆盖！错误状态丢失
```

**时序分析**：

- 当 `_handle_event` 抛出未捕获异常 → state 设为 `Error` → `break` 退出 while → `finally` 立即覆盖为 `Ready`
- 注意 L610-611 的 `if self._loop_running` 只在通过 `break` 正常退出 while 时才执行。异常路径在 `_handle_event` 内部已经 `break`，但此时 `_loop_running` 仍为 `True`，所以会先设 `Waiting`，再被 finally 覆盖为 `Ready`。无论如何结果都是 `Error` → `Ready`，错误状态被丢弃。

#### 位置 B：`run()` finally 块 (`bbagent/core/agent.py#L505-506`)

```python
# stream_tool_loop 异常处理 (L475-482)
except Exception as e:
    self.state = AgentState.Error        # ← 设置为 Error
    await self.hook.trigger(HookType.ON_ERROR, e)
    raise                                # ← 向上抛出

# run() 异常捕获 (L498-504)
except Exception as e:
    self.logger.error(...)
    raise                                # ← 继续向上抛出

# finally 块 (L505-506)
finally:
    self.state = AgentState.Ready        # ← 即使上面抛异常，这里也覆盖为 Ready
```

### 1.2 影响

- 前端点击 ▶ 启动 agent 后，如果输入通道初始化失败（比如 MCP 连接超时），后端 `start()` 中设置 `Error` 并 `return`，不经过 `_stream_loop`（此时还没进 while），反而能正确保持 Error 状态。
- 但如果 agent 已经在运行（`_stream_loop` 正常运转），处理事件时崩溃，则：
  - 前端先收到 `agent_state: error`（L603）— 显示红色 error 点
  - 然后收到 `agent_state: ready`（L619）— 红色点变灰色，看起来"一切正常"
  - 用户无法感知到 agent 已经崩溃
- 同理，`run()` 在 team 场景中被调用时，异常会被外层 handler 捕获，但 `finally` 已经把 state 设回 `Ready`，外层看到的是假状态。

### 1.3 修复方案

在 finally 中保留当前状态，不做无条件覆盖：

#### `_stream_loop` finally (L616-617)

```python
# 修改前：
finally:
    ...
    self.state = AgentState.Ready

# 修改后：
finally:
    ...
    if self.state != AgentState.Error:
        self.state = AgentState.Ready
```

#### `run()` finally (L505-506)

```python
# 修改前：
finally:
    self.state = AgentState.Ready

# 修改后：
finally:
    self.state = AgentState.Ready if self.state == AgentState.Running else self.state
```

或者更简洁：在 `finally` 前记录状态，`finally` 只在非 Error 时重置。

---

## 问题 2：_emit 字符串与 AgentState 枚举值不一致

### 2.1 现状

#### AgentState 定义 (`bbagent/core/agent.py#L55-59`)

```python
class AgentState:
    Ready = 'Ready'
    Waiting = 'Waiting'
    Running = 'Running'
    Error = 'Error'
```

#### _emit 调用使用硬编码小写字符串

| 位置 | 行号 | 硬编码值 |
|------|------|---------|
| `start()` | L542 | `'waiting'` |
| `start()` error | L553 | `'error'` |
| `_handle_event` running | L590 | `'running'` |
| `_handle_event` error | L603 | `'error'` |
| `_stream_loop` waiting | L612 | `'waiting'` |
| `_stream_loop` finally | L619 | `'ready'` |

共 6 处硬编码。

#### 后端 & 前端消费端

| 组件 | 文件 | 期望值 |
|------|------|--------|
| `agent_factory.get_state()` | `backend/factories/agent_factory.py#L798` | `raw_state.lower()` — 后端转换 |
| `chat.py` `subscribe_to()` | `backend/api/chat.py#L89` | `str(agent.state).lower()` — 后端转换 |
| `chat.py` global dispatcher | L88-92 | 透传 emit 的小写值 |
| `agent_factory` team state | L668-670 | `str(team.state).lower()` — 后端转换 |
| Team state check | L200 | `str(team.state).lower() == "ready"` |
| Frontend store | `store/index.ts#L149` | `"ready" \| "waiting" \| "running" \| "error"` |
| ChatWindow | `ChatWindow.tsx#L722` | `as "ready" \| "waiting" \| "running" \| "error"` |
| TeamGraphView | `TeamGraphView.tsx#L36` | `"ready" \| "waiting" \| "running" \| "error"` |

#### 当前一致性路径

```
Agent._emit('ready')  ──WS──► 前端 (小写, 直接匹配)        ✅
Agent._emit('waiting') ──WS──► 前端 (小写, 直接匹配)       ✅
Agent._emit('running') ──WS──► 前端 (小写, 直接匹配)       ✅
Agent._emit('error')   ──WS──► 前端 (小写, 直接匹配)       ✅

agent.state (AgentState.Running = 'Running') ──HTTP──► get_state().lower() → 'running' → 前端  ✅
```

**当前恰好是一致的**，因为 emit 刻意写成小写，后端 HTTP 侧也转换成了小写。但这种"碰巧一致"是脆弱的 —— 如果有人修改了 emit 字符串但忘记改 HTTP 转换，或者反过来，就会断裂。

### 2.2 问题

1. **硬编码分散**：6 处 emit 调用都是字符串字面量，修改 agent state 名称时容易遗漏。
2. **双重维护**：AgentState 定义了一套值，emit 用另一套值，中间靠人脑对齐。
3. **类型不安全**：emit 传入任意字符串，编译器/类型检查不会警告拼写错误。

### 2.3 修复方案

将 AgentState 的值改为小写，所有 emit 统一从 `self.state.value` 派生：

#### 方案 A（推荐）：AgentState 使用小写值

```python
# bbagent/core/agent.py
class AgentState:
    Ready = 'ready'
    Waiting = 'waiting'
    Running = 'running'
    Error = 'error'
```

所有 `_emit` 调用改为：

```python
await self._emit({'type': 'agent_state', 'state': self.state.value})
```

#### 后端适配

删除所有 `.lower()` 调用（约 6 处）：

| 文件 | 行号 | 改动 |
|------|------|------|
| `agent_factory.py` | L798 | `raw_state.lower()` → `raw_state` |
| `chat.py` | L89 | `str(agent.state).lower()` → `str(agent.state)` |
| `agent_factory.py` | L665, L668 | `str(team.state).lower()` → `str(team.state)` |
| `agent_factory.py` | L715 | `str(agent.state).lower()` → `str(agent.state)` |
| `team_conversation_factory.py` | L200, L247 | `str(team.state).lower()` → `str(team.state)` |

#### 前端

无需改动 —— 始终接收小写值。

### 2.4 收益

- **单一事实源**：状态字符串只在一处定义（AgentState 类）
- **编译时安全**：用 `self.state.value` 确保值一定来自枚举
- **后端简化**：不再需要到处 `.lower()`
- **新增状态**：只需在 AgentState 加一行，emit 自动跟进

---

## 影响范围汇总

### 问题 1（状态覆盖）

| 文件 | 改动 |
|------|------|
| `bbagent/core/agent.py#L616-617` | finally 中加 Error 判断 |
| `bbagent/core/agent.py#L505-506` | finally 中加状态判断 |

### 问题 2（大小写统一）

| 文件 | 改动 |
|------|------|
| `bbagent/core/agent.py#L55-59` | AgentState 值改为小写 |
| `bbagent/core/agent.py` | 6 处 _emit 改用 `self.state.value` |
| `backend/factories/agent_factory.py` | 3 处去掉 `.lower()` |
| `backend/api/chat.py` | 1 处去掉 `.lower()` |
| `backend/factories/team_conversation_factory.py` | 2 处去掉 `.lower()` |
| `frontend/` | 无改动 |

### 非目标

- 不改变 AgentState 的类结构（仍为 class 而非 enum.Enum，保持向后兼容）
- 不改变 WS 消息格式（前端零改动）
- 不改变 HTTP API 响应格式
