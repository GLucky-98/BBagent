# 全局 Template 配置 Agent 实现方案

## 背景

BBagent 目前支持用户手动创建单个 Agent，也支持创建由多个 Agent 组成的 AgentTeam。创建时需要用户理解较多配置项，例如系统提示词、工具、技能、hook、tool policy、team description、team members 和 contacts。对于熟悉框架的人来说，这些配置可以精细控制 Agent/Team 的能力；但对于普通用户来说，从一个自然语言需求出发手动设计这些配置，成本较高，也容易出现以下问题：

- 不知道应该创建单个 Agent 还是多个 Agent 组成的 Team。
- 不知道某类任务应该开启哪些工具、技能和 hook。
- 不知道 systemPrompt 应该包含哪些职责边界、输入输出约定和协作规则。
- 设计 Team 时容易把 contacts 做成全连接，或者遗漏必要的信息流转路径。
- 直接创建运行时 Agent 时，需要同时处理模型、工作目录、session、baseDir 等环境相关字段，容易把“能力设计”和“实例创建”混在一起。

因此需要一个系统级配置助手：用户用自然语言描述想要的能力，系统自动生成一份可理解、可导入、可验证的配置蓝图。

这个配置助手的第一阶段产物不应是已经创建好的 Agent/Team，而应是 Template。

Template 是当前系统已有的导入导出格式，用来描述 Agent/Team 的能力结构。它使用人类可读名称记录工具、技能和成员关系，不携带运行时 UUID、主模型、工作目录、session、state、baseDir 等实例字段。用户拿到 Template 后，可以继续通过现有 “From Template” 流程导入，并在导入过程中选择模型和工作目录。

也就是说，本 issue 要实现的是：

> 一个后端自动创建的全局 Template 配置 Agent。它根据用户需求生成 Agent/Team Template，校验 Template，并保存到 `templates/`，但不直接创建或修改普通 Agent/Team。

## 问题定义

当前系统缺少一个“从需求到 Template”的自动化层。用户如果想创建一个适合自己任务的 Agent/Team，需要先理解配置协议，再手动填写配置。这个过程本质上包含两类工作：

1. 能力设计：判断任务需要单 Agent 还是 Team，设计角色职责、工具权限、技能、hook、team 成员和通讯录。
2. 实例创建：选择模型、工作目录，生成运行时 id、session、baseDir，并持久化为后端 Agent/Team。

第一类工作适合由 LLM 辅助完成；第二类工作依赖当前环境和用户选择，应继续交给现有创建流程处理。

因此该全局配置 Agent 的职责边界是：

- 输入：用户的自然语言需求，以及当前环境中可用的工具、技能、hook、已有 Template。
- 输出：一份合法的 Agent Template 或 Team Template。
- 后置动作：调用校验工具检查 Template，校验通过后保存到 `templates/`。
- 不做：不选择主模型，不选择 workingDir，不创建 Agent/Team，不修改已有 Agent/Team。

这样可以把“能力蓝图生成”和“运行时实例创建”分开，降低自动化风险，也复用现有 Template 导入链路。

## 当前代码路径

### Template 类型定义

`frontend/src/types/index.ts` 定义了当前前端导入导出的 Template 结构：

```ts
export interface AgentTemplate {
  type: "agent";
  name: string;
  systemPrompt: string;
  tools: string[];
  skills: string[];
  hooks: string[];
  hookConfig: Record<string, unknown>;
  toolPolicy: Record<string, unknown>;
}

export interface TeamTemplate {
  type: "team";
  name: string;
  teamDescription: string;
  members: AgentTemplate[];
  contacts: Record<string, Record<string, string>>;
}
```

### Template 解析

`frontend/src/lib/utils.ts` 的 `resolveTemplate()` 负责把 Template 中的人类可读名称解析成当前环境里的 id：

- `tools`: tool name -> tool id
- `skills`: skill name -> skill id
- `hookConfig.submodelId`: model name -> model id
- `toolPolicy.subAgentModel`: model name -> model id
- `toolPolicy.subAgentBlockedTools`: tool name -> tool id

因此 Template 本身应继续使用名称而不是 UUID。

### Template 示例和兼容测试

`templates/CodeTeam_template.json` 是当前公开示例和兼容 fixture。

`tests/integration/test_template_codeteam.py` 验证了基本 shape：

- team template 有 `name`、`members`、`contacts`
- contacts 的 owner 必须是 member
- contact 目标必须是 member
- 不能包含 self contact
- template 可以构造成 core `AgentTeam`

## Template 参数清单

### Agent Template

```json
{
  "type": "agent",
  "name": "AgentName",
  "systemPrompt": "...",
  "tools": ["read", "grep"],
  "skills": [],
  "hooks": ["built_in.compress"],
  "hookConfig": {},
  "toolPolicy": {}
}
```

字段含义：

- `type`: 固定为 `"agent"`。
- `name`: Agent 的人类可读名称。
- `systemPrompt`: 角色、职责、能力边界、工作方式、输出格式和协作规则。
- `tools`: 工具名称列表，不是 tool id。
- `skills`: 技能名称列表，不是 skill id。
- `hooks`: hook 名称列表。
- `hookConfig`: hook 参数配置。模型引用应使用模型名称，导入时再解析。
- `toolPolicy`: 工具策略配置。工具或模型引用应使用名称，导入时再解析。

不应包含：

- `id`
- `modelId`
- `workingDir`
- `baseDir`
- `lastSessionId`
- `state`
- `started`
- `memberIds`

当前导出逻辑可能附带 `_modelName` 作为人类参考字段，但主模型不属于 Template 的能力结构，配置 Agent 不应依赖它生成可执行配置。

### Team Template

```json
{
  "type": "team",
  "name": "TeamName",
  "teamDescription": "...",
  "members": [AgentTemplate],
  "contacts": {
    "AgentA": {
      "AgentB": "AgentB 对 AgentA 的角色描述"
    }
  }
}
```

字段含义：

- `type`: 固定为 `"team"`。
- `name`: Team 的人类可读名称。
- `teamDescription`: 团队使命、协作原则、工作流程和通讯规范，会进入 team prompt。
- `members`: 成员 Agent Template 列表。
- `contacts`: 有向通讯录。`A -> B` 表示 A 能看到并联系 B，描述文本会进入 A 的 teammate prompt。

contacts 约束：

- owner 必须是成员名。
- contact 目标必须是成员名。
- owner 不能联系自己。
- 不默认全连接，应根据工作流和职责依赖设计。

## 目标

- 后端启动时，如果当前环境存在可用模型，自动确保一个全局 Template 配置 Agent。
- 该 Agent 的职责是把自然语言需求转换为可导入、可验证、可解释的 Agent/Team Template。
- 该 Agent 不直接创建普通 Agent/Team。
- 该 Agent 不修改已有 Agent/Team 配置。
- 该 Agent 能查询当前可用工具、技能、hook 和已有 Template，避免虚构能力或重复命名。
- 该 Agent 能校验 Template，并把通过校验的 Template 保存到 `templates/`。
- 成功输出应包含设计说明、Template 摘要、保存路径和校验结果。

## 非目标

- 第一阶段不实现运行诊断 Agent。
- 第一阶段不实现结构优化 Agent。
- 第一阶段不根据运行日志自动修改 Agent/Team。
- 第一阶段不改变现有 Template 导入流程。
- 第一阶段不要求 Template 携带主模型或工作目录。
- 第一阶段不要求前端新增复杂交互；可先通过普通对话和保存文件完成闭环。

## 推荐方案

### 1. 新增全局 Agent 管理模块

建议新增：

```text
backend/global_agents/
  __init__.py
  template_config_agent.py
  template_tools.py
  template_validation.py
  prompts.py
```

职责拆分：

- `template_config_agent.py`: 确保全局 Template 配置 Agent 存在。
- `template_tools.py`: 提供该 Agent 可用的后端工具。
- `template_validation.py`: Template 结构和资源引用校验。
- `prompts.py`: 存放系统提示词和内置 Template schema 说明。

在 `State.__init__` 中创建 manager，或在 `State.load_all()` 末尾惰性调用：

```python
await self.global_agent_manager.ensure_template_config_agent()
```

调用位置应在以下加载完成之后：

- model factory
- tool factory
- skill factory
- hook descriptors 可访问
- agent factory
- team factory

### 2. 全局 Agent 身份

建议给全局 Agent 使用稳定身份：

```text
id: global-template-config-agent
name: Template Config Assistant
systemRole: template_config_assistant
systemManaged: true
```

当前 `AgentConfig` 尚无 `systemManaged` / `systemRole` 字段。建议扩展：

```python
systemManaged: bool = False
systemRole: str = ""
```

兼容性：

- Pydantic 当前 `AgentConfig` 使用 `extra="ignore"`，旧配置不会受影响。
- 新字段需要在 agent config 落盘、读取、列表返回时保留。
- UI 可第一阶段不特殊展示；后续再加系统标记和删除保护。

如果暂不扩 schema，也可以先通过稳定 id/name 识别，但不利于后续三个全局 Agent 共用。

### 3. 自动创建条件

后端启动时自动确保该 Agent：

- 如果没有任何模型配置，跳过创建并记录日志。
- 如果已有 `systemRole == "template_config_assistant"` 的 Agent，校验并补齐系统工具和提示词。
- 如果没有，则选择一个可用模型创建。
- 使用最小运行时工具集，只给它 Template 相关工具，不给文件编辑、bash 等通用工具。

模型选择规则第一版可以保守：

1. 如果后续引入默认模型设置，优先使用默认模型。
2. 当前没有默认模型设置时，选择 `model_factory.list_all()` 的第一个模型。
3. 不把该模型写入 Template 产物，仅用于全局 Agent 自身运行。

### 4. 系统提示词内容

`get_template_schema` 不做成工具，Template schema 和设计原则直接固化进系统提示词，因为它是稳定协议，不需要反复调用。

系统提示词至少包含以下内容。

#### 角色定位

你是 Template 配置助手，负责根据用户需求生成可导入的 BBagent Agent/Team Template。

你不直接创建普通 Agent/Team，不修改已有 Agent/Team，不生成运行时 id、主模型、工作目录、session、state 或 baseDir。

#### Agent/Team 判断原则

- 单一职责、单一执行者、独立完成任务：生成 `agent` template。
- 多角色分工、阶段性流程、需要成员协作：生成 `team` template。
- 用户明确要求团队、多个角色、协作流程：生成 `team` template。
- 用户需求模糊但可以由单一角色完成：优先生成保守的 `agent` template。
- 只有在缺少关键目标、领域或权限信息导致无法合理生成时，才向用户追问。

#### 工具权限策略

- 阅读、分析、检索类 Agent：优先使用 `read`、`grep`、`find`、`ls`。
- 写作、文档、产物生成类 Agent：在需要时加入 `write`。
- 修改已有文件类 Agent：在明确需要修改时加入 `edit`。
- 命令执行、测试、构建、脚本运行类 Agent：在明确需要时加入 `bash`。
- 复杂任务拆分或需要内部子任务时：在有明确理由时加入 `sub_agent`。
- 不明确需求时遵循最小权限原则，不默认给 `bash`、`write`、`edit`。
- 给出高权限工具时，在设计说明中解释理由。

#### Hook 策略

- `built_in.compress`: 长任务、复杂任务、team、多轮协作默认考虑启用。
- `built_in.memory`: 需要长期偏好、项目经验沉淀、反复复用的 Agent 才启用。
- 一次性任务 Template 不默认启用 memory。
- `hookConfig` 默认 `{}`，除非用户明确要求特殊配置。

#### Team contacts 策略

- contacts 是有向通讯录，不默认全连接。
- 按工作流、职责依赖和信息反馈路径设计。
- 上游可以联系下游传递交付物。
- 下游可以联系上游澄清输入、反馈阻塞或请求决策。
- 协调者、负责人或调度者可以拥有更多联系人。
- contact 描述应说明“对方在当前关系中的作用”，避免泛泛职位名。

#### 输出要求

成功生成时，最终回复包含：

- 设计说明。
- Template 类型和核心结构摘要。
- 校验结果。
- 保存路径。

Agent 在保存前必须调用 `validate_template`。校验失败时不得调用 `save_template`，应说明错误并给出修正后的方案。

### 5. 工具设计

第一版工具集：

```text
list_available_tools
list_available_skills
list_available_hooks
list_templates
read_template
validate_template
save_template
```

不提供：

```text
create_agent
update_agent
delete_agent
create_team
update_team
delete_team
```

这样可以把第一个全局 Agent 的边界稳定在 Template 生成，不提前进入实例管理。

#### list_available_tools

返回当前环境可用于 Template 的工具名称、来源、描述和风险提示。

数据来源：

- `state_manager.list_tools()`
- 或直接读取 `tool_factory` 配置

返回示例：

```json
[
  {
    "name": "read",
    "source": "built_in",
    "description": "...",
    "risk": "read_only"
  }
]
```

风险等级可先由后端硬编码：

- `read_only`: `read`、`grep`、`find`、`ls`
- `write`: `write`、`edit`
- `execute`: `bash`
- `delegation`: `sub_agent`
- `external`: web 或 MCP 工具
- `unknown`: 未分类

#### list_available_skills

返回当前可用技能：

```json
[
  {
    "name": "skill-name",
    "description": "...",
    "path": "..."
  }
]
```

Template 使用 `name` 引用。

#### list_available_hooks

返回 hook 名称、说明和可配置字段。

数据来源优先复用现有 hooks API 的 descriptor 逻辑，避免重复定义。

返回示例：

```json
[
  {
    "name": "built_in.compress",
    "description": "...",
    "fieldSections": []
  }
]
```

#### list_templates

列出 `templates/` 下已有 template 文件：

```json
[
  {
    "name": "CodeTeam",
    "type": "team",
    "path": "templates/CodeTeam_template.json"
  }
]
```

用途：

- 避免重复命名。
- 让配置 Agent 可以参考已有模板。

#### read_template

读取指定 Template 文件内容。

限制：

- 只能读取 `templates/` 下的 `.json` 文件。
- 路径必须规范化并限制在 templates 目录内。

用途：

- 用户要求“参考某个模板”时读取。
- 生成相似模板时复用结构。

#### validate_template

输入：完整 Template JSON object。

输出：

```json
{
  "valid": true,
  "errors": [],
  "warnings": []
}
```

错误阻止保存，警告允许保存。

errors：

- JSON 结构不是 object。
- `type` 不是 `agent` 或 `team`。
- 缺少必填字段。
- 字段类型错误。
- agent `name` 为空。
- team `members` 为空。
- team 成员名重复。
- contacts owner 不存在于 members。
- contacts target 不存在于 members。
- contacts 包含 self contact。
- tools 引用了不存在的工具名称。
- skills 引用了不存在的技能名称。
- hooks 引用了不存在的 hook 名称。
- `toolPolicy.subAgentBlockedTools` 引用了不存在的工具名称。
- `toolPolicy.subAgentModel` / `hookConfig.submodelId` 引用了不存在的模型名称时，第一版可作为 warning；如果希望严格导入，则升级为 error。

warnings：

- agent 没有任何工具。
- team 只有一个成员。
- team contacts 为空。
- contacts 过密，接近全连接。
- 使用 `bash` 但 systemPrompt 没有命令执行边界。
- 使用 `write` / `edit` 但 systemPrompt 没有写入边界。
- hook 启用了 `built_in.memory` 但职责看起来是一次性任务。
- 成员职责描述明显过短。

#### save_template

输入：

```json
{
  "template": {},
  "filename": "MyTemplate_template.json",
  "overwrite": false
}
```

行为：

- 保存前内部再次调用同一套校验逻辑。
- 只写入 `templates/` 目录。
- 文件名只允许安全字符，默认规范化为 `{TemplateName}_template.json`。
- `overwrite=false` 时，如果文件已存在返回错误。
- 写入格式为 `json.dumps(..., indent=2, ensure_ascii=False)`。

输出：

```json
{
  "success": true,
  "path": "templates/MyTemplate_template.json",
  "warnings": []
}
```

## Template 校验实现建议

`template_validation.py` 提供纯函数，便于测试：

```python
def validate_template(
    template: dict,
    *,
    tool_names: set[str],
    skill_names: set[str],
    hook_names: set[str],
    model_names: set[str] | None = None,
) -> TemplateValidationResult:
    ...
```

`TemplateValidationResult` 可用 Pydantic 或 dataclass：

```python
class TemplateValidationResult(BaseModel):
    valid: bool
    errors: list[str] = []
    warnings: list[str] = []
```

第一阶段建议手写结构校验，不引入额外 JSON Schema 依赖。原因：

- 当前结构简单。
- contacts 和资源引用需要业务规则校验。
- 更容易输出面向模型可修正的错误信息。

## 与前端导入流程的关系

第一阶段不需要重写导入流程。

生成后的文件进入 `templates/`，用户可以通过当前 “From Template” 入口选择并导入。导入后：

- Agent Template 的 `modelId` 仍为空，由用户选择。
- Team Template 的 member `modelId` 仍为空，由用户选择。
- `workingDir` 仍为空，由用户选择。
- tools/skills/hook 名称由现有 `resolveTemplate()` 解析成 id。

后续可以考虑增加“从配置助手生成后直接打开导入弹窗”的前端体验，但不属于第一阶段。

## 运行时安全

- 全局 Template 配置 Agent 只拥有 Template 工具，不拥有通用文件写入、bash、agent/team CRUD 工具。
- `save_template` 只能写入 `templates/`。
- `read_template` 只能读取 `templates/`。
- `validate_template` 在保存前必须重复执行，不能只依赖 Agent 自觉调用。
- 第一阶段不允许覆盖已有模板，除非用户明确要求并传 `overwrite=true`。

## 测试计划

### 单元测试

新增 `tests/unit/backend/test_template_validation.py`：

- valid agent template 通过。
- valid team template 通过。
- unknown tool 返回 error。
- unknown skill 返回 error。
- unknown hook 返回 error。
- contacts owner 不存在返回 error。
- contacts target 不存在返回 error。
- self contact 返回 error。
- duplicate member name 返回 error。
- bash without prompt boundary 返回 warning。
- empty contacts for multi-member team 返回 warning。

新增 `tests/unit/backend/test_template_tools.py`：

- list tools 返回名称而不是 id。
- validate_template 工具返回稳定结构。
- save_template 写入 `templates/`。
- save_template 拒绝路径穿越。
- save_template 拒绝覆盖已有文件。
- read_template 拒绝 templates 目录外路径。

### 集成测试

新增或扩展后端启动相关测试：

- 有模型配置时，`ensure_template_config_agent()` 创建全局 Agent。
- 无模型配置时，不创建并不报错。
- 重复调用不会重复创建。
- 已存在全局 Agent 时会复用并补齐配置。
- 全局 Agent 不获得通用 `bash`、`write`、`edit` 工具，只获得 Template 工具。

### 兼容测试

保留并扩展 `tests/integration/test_template_codeteam.py`：

- `CodeTeam_template.json` 仍能通过新的 `validate_template()`。
- 现有 contacts shape 规则保持兼容。

## 质量门

实现完成后至少运行：

```bash
python -m pytest tests/unit/backend/test_template_validation.py
python -m pytest tests/unit/backend/test_template_tools.py
python -m pytest tests/integration/test_template_codeteam.py
ruff check backend tests
```

如果修改 `AgentConfig` schema 或前端类型：

```bash
python -m pytest tests
ruff check backend bbagent tests
mypy bbagent backend
cd frontend
npm run lint
npm run build
```

## 分阶段落地

### Phase 1: Template 校验和工具

- 新增 `template_validation.py`。
- 新增 Template 工具。
- 增加单元测试。
- 不接入全局 Agent 自动创建。

### Phase 2: 全局 Template 配置 Agent

- 新增系统提示词。
- 新增 manager。
- 启动时自动确保 Agent。
- 只挂载 Template 工具。
- 增加启动和幂等测试。

### Phase 3: 前端体验增强

- 可选展示 system-managed 标识。
- 可选提供“配置助手生成模板后打开导入”的入口。
- 可选在 Template Picker 中展示生成来源和校验状态。

## 待确认问题

- 是否立刻给 `AgentConfig` 增加 `systemManaged` / `systemRole` 字段，还是第一版先用稳定 id/name。
- 模型名称引用在 `toolPolicy.subAgentModel` / `hookConfig.submodelId` 中找不到时，是 error 还是 warning。
- `save_template` 是否允许覆盖已有模板；建议默认不允许，仅在用户明确要求时允许。
- 全局 Agent 是否在普通 Agent 列表中展示系统标识；建议先可见，后续增加删除保护。
