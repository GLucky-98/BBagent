# Context Compress 单阈值合并方案

## 背景

`bbagent/built_in_hook/ctx_compress_hook.py` 的 `compress_session()` 在 `pending_zone` 上对未压缩的 turn 做分组,然后对每组调用 `SubAgent` 生成摘要。分组逻辑位于 [Phase 3](file:///Users/gl/Desktop/BBagent/BBagent/bbagent/built_in_hook/ctx_compress_hook.py#L107-L136),代码如下:

```python
small_turn_threshold = min(int(merge_threshold / 3), small_turn_cap)

for turn in uncompressed_turns:
    t = turn.token_count
    if t < small_turn_threshold:                 # 小 turn
        if current_group_tokens + t <= merge_threshold:
            current_group.append(turn)
            current_group_tokens += t
        else:
            if current_group:
                groups.append(current_group)
            current_group = [turn]
            current_group_tokens = t
    else:                                         # 大 turn,强制独立
        if current_group:
            groups.append(current_group)
        groups.append([turn])
        current_group = []
        current_group_tokens = 0
```

涉及的两个关键参数:

| 参数 | 默认值 | 来源 |
|---|---|---|
| `merge_ratio` | 0.2 | 推导 `merge_threshold = max_context_tokens * merge_ratio` |
| `small_turn_cap` | 5000 | 推导 `small_turn_threshold = min(merge_threshold / 3, small_turn_cap)` |

## 问题

### 1. 合并组粒度可以超过"大 turn"判定边界

`merge_threshold` 和 `small_turn_threshold` 是两个相互独立的阈值,数值关系在 `small_turn_cap` 较小时会失衡:

假设 `max_context_tokens = 100 000` (常见模型上下文):

| 量 | 值 |
|---|---|
| `merge_threshold` | 20 000 |
| `small_turn_threshold` | min(6 666, 5000) = **5 000** |
| "大 turn" 判定 | ≥ 5 000 |
| 小 turn 合并组上限 | 20 000 |

那么:

- 一个 **5 001 token** 的 turn → 单独成一组,独占一次 LLM 调用,粒度 5k。
- 四个 **4 999 token** 的小 turn → 合并成一组,一次调用,粒度 ~20k。

合并后的小 turn 组在压缩粒度上**比独立的大 turn 粗 4 倍**。这和注释里"避免吞掉过多上下文"的初衷相悖。

### 2. 设计意图和实现脱节

代码想表达的语义是:

> 小 turn 信息密度低、上下文相关 → 合并节省调用次数;
> 大 turn (工具输出、代码) 信息密度高 → 单独保留细节。

但**实现用 token 数 + 一个硬上限**做分类,导致:

- 一个 5k 的纯闲聊 turn 被当"大 turn"独立压,反而浪费调用。
- 一个合并组里如果混入一个本不该合并的高密度 turn (例如 < 5k 的 JSON 配置),它会和周围闲聊一起糊成一份粗粒度摘要,细节丢失。

### 3. 同一逻辑在 memory 子系统中重复存在,且耦合配置

`bbagent/built_in_hook/memory/memory_hook.py` 的 `_group_turns_for_extraction()` ([L227-L262](file:///Users/gl/Desktop/BBagent/BBagent/bbagent/built_in_hook/memory/memory_hook.py#L227-L262)) 用**完全相同**的 `small_turn_threshold` + `merge_threshold` 双阈值逻辑,且两者共用 `BuiltinHookConfig.merge_ratio` 和 `BuiltinHookConfig.small_turn_cap` ([bbagent/built_in_hook/__init__.py#L147-L151](file:///Users/gl/Desktop/BBagent/BBagent/bbagent/built_in_hook/__init__.py#L147-L151))。

这意味着:

- 任何对阈值的修改必须同时影响两个子系统才能保持一致行为。
- 两个子系统本来有不同诉求 (compress: 控制摘要调用的输入规模; extract: 控制抽取调用的输入规模),却被一个 `small_turn_cap` 绑死。

### 4. 没有针对该逻辑的单元测试

`tests/unit/built_in_hook/` 下没有 `test_ctx_compress_*`,memory hook 已有 `test_memory_optimization.py` 但未覆盖 `_group_turns_for_extraction` 的边界行为。重构时缺乏回归保护。

## 目标

- 把 ctx compress 的分组逻辑收敛到**单个阈值** `merge_threshold`。
- 消除"合并组粒度 > 独立大 turn 粒度"的不对称。
- 顺手处理 memory 子系统中的相同逻辑,避免两套实现继续漂移。
- 保留对超大单 turn (单 turn token > `merge_threshold`) 的兜底,确保极端情况不退化。
- 为新增 / 修改的逻辑加单元测试。

## 非目标

- 不改变 `compress_session` 的整体阶段划分 (Phase 0–6) 和 Phase 5 的"整组跳过"语义。
- 不改变 `Turn.is_summarized` / `Turn.summary` / `Turn.summary_group_id` / `Turn.skip_summary` 等已持久化字段。
- 不修改 `compress_prompt` / `compress_prefix` 文案。
- 不调整 `keep_recent_turns` / `compression_threshold` 语义。
- 不改变 `SubAgent` 调用接口和重试逻辑。
- 不重构 `agent.session.turns` 的存储结构。
- 不修改前端对压缩相关事件的展示。

## 推荐方案

### 1. ctx compress 分组改用单阈值

把 `bbagent/built_in_hook/ctx_compress_hook.py` 中的 Phase 3 分组改为:

```python
merge_threshold = int(max_context_tokens * merge_ratio)
# 删除 small_turn_threshold / small_turn_cap 的计算

groups = []
current_group: list[Turn] = []
current_group_tokens = 0

for turn in uncompressed_turns:
    t = turn.token_count
    if current_group_tokens + t <= merge_threshold:
        current_group.append(turn)
        current_group_tokens += t
    else:
        if current_group:
            groups.append(current_group)
        # t 自身可能 > merge_threshold,此时 current_group 已被 flush,
        # 新组里只剩这一个 turn,自然满足"每组 token ≤ merge_threshold" 的弱保证。
        current_group = [turn]
        current_group_tokens = t

if current_group:
    groups.append(current_group)
```

**为什么不需要单独的"大 turn"分支**:

- 单 turn `t > merge_threshold` 时,`current_group_tokens + t > merge_threshold`,必然走 else 分支。
- else 分支先 flush 旧组,再以 `t` 初始化新组,新组 token = t。
- 因此"超大单 turn"会被独立成一组,下一轮合并从它之后重新开始。
- 不会出现"把超大 turn 塞进已满的旧组"或"在超大 turn 后丢弃后续 turn"。

**语义变化**:

| 场景 (turn 序列, merge_threshold = 20k) | 旧行为 | 新行为 |
|---|---|---|
| [4k, 4k, 4k, 4k, 4k] | [4+4+4+4][4] = 2 组 | [4+4+4+4+4] = 1 组 |
| [4k, 4k, 5k, 4k, 4k] | [4+4][5][4+4] = 3 组 | [4+4+5+4+4] = 1 组 (21k? 见下) |
| [25k] | [25] = 1 组 | [25] = 1 组 |
| [4k, 25k, 4k] | [4][25][4] = 3 组 | [4][25][4] = 3 组 |
| [10k, 10k, 10k] | [10+10][10] = 2 组 | [10+10][10] = 2 组 |
| [12k, 12k, 12k] | [12+12][12] = 2 组 | [12+12][12] = 2 组 |

注:第二个例子旧行为 3 组、新行为 1 组 21k (超 20k)。需要修正判定条件为严格小于或显式限流:

```python
if t <= merge_threshold - current_group_tokens:
    current_group.append(turn)
    current_group_tokens += t
else:
    ...
```

或保持 ≤ 但允许 1 token 抖动。无论哪种,都**比现状的粒度更一致**——任意一组的 token 都不超过 `merge_threshold` + 单 turn 自身上限。

### 2. memory 同步改造

把 `bbagent/built_in_hook/memory/memory_hook.py` 的 `_group_turns_for_extraction()` 改成与 ctx compress 一致的单阈值版本。这样:

- 两个子系统的"组大小"语义统一,不再受 `small_turn_cap` 影响。
- `BuiltinHookConfig.small_turn_cap` 字段可以废弃 (见下文兼容性)。

`do_extract_turns()` 中的 `merge_ratio` / `small_turn_cap` 参数同步收敛:

```python
merge_threshold = int(max_context_tokens * merge_ratio)
groups = _group_turns_for_extraction(turns, merge_threshold)
```

### 3. 兼容性策略

`BuiltinHookConfig.merge_ratio` 保留 (compress 和 extract 都需要);`small_turn_cap` 设为**软废弃**:

- 字段仍保留在 `BuiltinHookConfig` 上,默认值仍为 5000。
- 在两个子系统的实现中**不再读取**该字段。
- 文档 / docstring 标注 "deprecated, ignored since X"。
- 不抛错、不警告日志,保持静默迁移,避免对老配置文件造成 runtime error。

理由:

- 用户的 `config.json` / 模板里可能显式写了 `small_turn_cap`,直接抛错会影响存量配置。
- 该字段不再影响行为,但保留字段本身对未来可能新增的"内容类型"分类 (例如 code block 长度识别) 留口子。

如果团队倾向激进清理,可以直接删除字段。决定前应在 PR 中确认存量 `data/` 下用户配置里是否实际使用了 `small_turn_cap`。

### 4. 单测覆盖

新增 `tests/unit/built_in_hook/test_ctx_compress_grouping.py`,覆盖以下场景 (使用 `DummyModel` 替换 `SubAgent.run`,参考 `test_memory_optimization.py` 的 DummyLogger 模式):

| 用例 | 输入 | 期望分组 |
|---|---|---|
| 全部小 turn 累加 | [4k] * 5, mt=20k | 1 组 [20k] |
| 触发开新组 | [4k] * 6, mt=20k | 2 组 [20k][4k] |
| 单 turn 超大 | [25k], mt=20k | 1 组 [25k] |
| 超大 turn 夹在中间 | [4k, 25k, 4k], mt=20k | 3 组 [4k][25k][4k] |
| 边界相等 | [20k, 1], mt=20k | 2 组 [20k][1] |
| 空输入 | [], mt=20k | 0 组 |
| 单 turn 恰好等于 mt | [20k], mt=20k | 1 组 [20k] |

测试通过 hook 函数 `create_ctx_compress_hook` 入口不方便直接调内部 group 逻辑,推荐:

- 把 group 逻辑抽取为模块级私有函数 `_group_turns_for_compress(turns, merge_threshold)`,再在 `compress_session()` 中调用。
- 测试直接调这个函数,绕开 `SubAgent` 依赖。

同理,`_group_turns_for_extraction` 在 memory 子系统中抽取后,加对应测试。

### 5. 日志和可观测性

现有日志字段 `"groups formed from N turns"` 保留。新增:

- 单 turn 超大时打 warning,提示本次未参与合并。
- 单组合并数 (turn count) > 5 时打 info,便于观察是否出现"过粗合并"。

示例:

```python
if turn.token_count > merge_threshold:
    logger.warning(
        f"Turn exceeds merge_threshold ({turn.token_count} > {merge_threshold}), standalone group",
        context={...},
    )
```

## 兼容性风险评估

| 风险点 | 影响 | 缓解 |
|---|---|---|
| 已有会话重载后 `Turn.summary_group_id` 仍然指向旧分组 | 老 turn 仍按旧逻辑压缩,新 turn 按新逻辑 | 不影响功能;新压缩在 memory_extracted=False 的 turn 上触发,老已压缩 turn 不再处理 |
| 用户在 config 显式设置 `small_turn_cap` | 字段被忽略,但不报错 | 字段软废弃;文档说明 |
| 真实场景合并粒度变粗 (例 [4k]*5 → 1 组 20k) | LLM 摘要质量可能下降 | 通过测试用例 + 在大窗口场景下人工观察摘要质量;若回归严重,可降低 `merge_ratio` (0.2 → 0.15) 缓解 |
| 真实场景合并粒度变细 (例 [4k,5k,4k] → 旧 3 组 vs 新 1 组) | 摘要调用次数减少,成本下降 | 这是预期收益 |
| Phase 5 "整组跳过" 仍按 `summary_group_id` 工作 | 不受影响 | 新旧逻辑下 group_id 语义不变 |

## 实施步骤建议

1. **抽函数**: 在 `ctx_compress_hook.py` 内把 Phase 3 分组抽为 `_group_turns_for_compress(turns, merge_threshold) -> list[list[Turn]]`。
2. **改实现**: 替换为单阈值版本。
3. **同步 memory**: 改 `_group_turns_for_extraction` 为相同单阈值签名,删除 `small_turn_threshold` 入参。
4. **去读 `small_turn_cap`**: `do_extract_turns` 和 `compress_session` 不再读该字段。
5. **加日志**: 在超大 turn 处打 warning,在组合并数 > 5 时打 info。
6. **加测试**: 写 `test_ctx_compress_grouping.py` 与 `test_memory_grouping.py` (或合并到一个文件)。
7. **跑质量门**: `ruff check bbagent/built_in_hook tests/unit/built_in_hook` + `python -m pytest tests/unit/built_in_hook tests/unit/built_in_tool`。
8. **回归**: 若用户数据中有真实会话,跑一次完整压缩链路 (mock LLM) 确认 Phase 5 group 跳过仍正确。

## 验收

- `small_turn_cap` 字段保留,但 compress 与 memory 实现中不再读取。
- 新增单元测试覆盖上述 7 个分组场景,全部通过。
- 现有 `test_memory_optimization.py` 全绿。
- `python -m pytest tests` 全绿。
- `ruff check .` 无新增告警。
- 人工 spot check: 用一份真实长会话 (或构造的 ≥ 20 turn 测试数据) 跑一次压缩,对比新旧实现下产生的 group 数、每次摘要的输入 token 数、生成的摘要长度。
