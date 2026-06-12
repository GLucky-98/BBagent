# BBagent

> **Building Block Agent** — Stack Agents, Compose Teams
>
> 像搭积木一样搭建、运行、调试 Agent 与 Agent Team。

[![License: MIT](https://img.shields.io/badge/License-MIT-0066cc.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-0066cc.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-149eca.svg)](https://react.dev/)

BBagent 是一个自己实现的智能体开发框架：核心库不依赖 LangChain / AutoGen / CrewAI 等外部 Agent 封装库，后端基于 FastAPI，前端提供一个可运行多 Agent / Team 的 Web Workspace。

它的目标不是把 Agent 包成黑盒，而是把 Agent、Team、Session、Tool、Hook、MCP、Skill 拆成可以组合、可以调试、可以长期演化的 building blocks。

## Key Features

| 能力 | 说明 |
|---|---|
| Composable Agent Core | Agent、Session、Tool、Hook、MCP、Skill 都是仓库内直接实现的可组合模块 |
| AgentTeam | 通过 `contacts` 描述多 Agent 通讯图，运行时注入 `send_message` / `broadcast` |
| Session Fork | Session 是可保存、加载、跨 Agent 传递和分叉的全局上下文资产 |
| Web Workspace | 用 React + FastAPI 管理 Model、Agent、Team、Skill、MCP、Prompt 和运行会话 |
| Built-in Tools | 内置 read/write/edit/bash/grep/find/ls/sub_agent/web_search/fetch_url 等 agent 原子工具 |
| Hooks & Memory | 支持上下文压缩、长期记忆等生命周期扩展能力 |

## Architecture

```mermaid
flowchart LR
    UI["React Web Workspace"] --> API["FastAPI Backend"]
    API --> State["State Manager & Factories"]
    State --> Data["data/ runtime configs and sessions"]
    State --> Core["bbagent Core"]
    Core --> Agent["Agent"]
    Core --> Team["AgentTeam"]
    Core --> Session["Session"]
    Agent --> Model["Model Providers"]
    Agent --> Tools["Tools"]
    Agent --> Hooks["Hooks"]
    Agent --> MCP["MCP Clients"]
    Agent --> Skills["Skills"]
    Team --> Agent
```

## Why BBagent

### 1. AgentTeam 自由搭建

BBagent 的 Team 不是固定的 sequential / supervisor 模板。每个 Agent 通过 `contacts` 声明自己能联系谁、对方是什么角色，Team 运行时根据这张通讯录图注入 `send_message` / `broadcast` 工具。

这意味着中心式、圆桌式、混合式协作都可以用同一套机制表达：

```text
Supervisor -> Worker A
Supervisor -> Worker B

Analyst -> Architect -> Developer
Developer -> Reviewer
Developer -> Tester
Reviewer -> Architect
```

仓库里预置了一个 `CodeTeam` 示例，包含 `Analyst / Architect / Developer / Reviewer / Tester / Documenter` 六个成员。

![CodeTeam team chat and graph view](assets/readme/team-view.png)

`contacts` 配置在 Web Workspace 中可以直接编辑：每个成员只看到被授权联系的队友，并带着对方在当前协作图里的角色描述。

![Configure Team contacts](assets/readme/team-contact.png)

### 2. Session 是全局上下文资产

在 BBagent 里，`Session` 不是某个 Agent 私有的聊天记录，而是一个可以保存、加载、传递、fork 的上下文资产。

你可以让 Agent A 先分析问题，再把同一个 Session 交给 Agent B 继续处理；也可以在某个 turn 分叉出多条探索路线。这个设计适合长任务、多 Agent 协作、方案对比和可回放调试。

![Session history and fork controls](assets/readme/sessionfork.png)

### 3. 核心库小而可改

核心实现位于 [`bbagent/`](bbagent/)，Agent 循环、消息结构、Tool、Hook、MCP、Skill、Team 都在仓库内直接实现。你可以把它作为独立 Python 包嵌入自己的项目，也可以直接阅读和修改核心流程。

```python
from bbagent.core.agent import Agent, AgentConfig
from bbagent.core.message import Session
```

### 4. Web Workspace

BBagent 不只是一个 SDK。仓库内置 FastAPI 后端和 React 前端，支持在 Web UI 中配置 Model、Agent、Skill、MCP、Prompt，并在多个 Agent / Team 之间切换。

后端会从 `data/` 加载已有配置；Agent 运行过程中的 session、日志和团队消息会持久化到本地目录。

![Configure an Agent with tools, hooks, and skills](assets/readme/configure-agent.png)

### 5. 全流程可观测

Agent 系统最难的是调试。BBagent 会把会话、工具调用、Hook 行为、长期记忆等运行痕迹落盘，便于定位问题、回放上下文和比较不同 Agent 配置的行为差异。

### 6. 内置原子工具与 Hook 子系统

BBagent 预置了一组 coding agent 常用的原子工具，以及两个已经落地的 Hook 子系统：上下文压缩和长期记忆。它们展示了 BBagent 的扩展机制不是摆设，而是可以直接承载真实 Agent 能力。

## Core Concepts

| 概念 | 作用 |
|---|---|
| `Agent` | 单个智能体，持有模型、系统提示词、工具、Hook、Session |
| `AgentTeam` | 多 Agent 协作容器，通过 `contacts` 决定可见队友和消息路由 |
| `Session` | 全局上下文资产，可保存、加载、跨 Agent 传递、fork |
| `Tool` | 一次动作，例如读文件、写文件、执行命令、搜索内容 |
| `Hook` | 生命周期扩展点，用来在输入、模型调用、工具调用、错误处理等阶段插入逻辑 |
| `MCP` | Model Context Protocol 客户端，用于接入外部工具服务 |
| `Skill` | 文件夹式能力包，用来组织 prompt、工具和配置 |

## Built-in Building Blocks

### Atomic Tools

BBagent 内置 10 个原子工具，覆盖 coding agent 和联网检索最常见的基础动作。它们保持小而可组合，不把业务流程封装进工具本身。

| 工具 | 作用 |
|---|---|
| `read` | 读取文件 |
| `write` | 写入文件 |
| `edit` | 替换文本或正则匹配 |
| `bash` | 执行 shell 命令 |
| `grep` | 搜索文件内容 |
| `find` | 查找文件 |
| `ls` | 列出目录 |
| `sub_agent` | 派生子 Agent 执行隔离任务 |
| `web_search` | 搜索网页并返回标题、链接和摘要 |
| `fetch_url` | 抓取 URL 并返回可读文本内容 |

这些工具可以通过 `Policy` 控制读取大小、命令超时、输出截断、工作目录和联网边界，让 Agent 的执行边界更清楚。

### Built-in Hooks

BBagent 预置两个 Hook 子系统：

| Hook | 作用 |
|---|---|
| `built_in.compress` | 在上下文接近模型窗口时压缩旧 Session 内容 |
| `built_in.memory` | 为 Agent 增加长期记忆写入、提取、清理和检索注入能力 |

`built_in.compress` 注册在 `BEFORE_STREAM` 阶段。它会在每次模型流式调用前判断当前 Session 是否接近模型上下文上限，并在需要时压缩旧 turn，让上下文管理成为 Agent 生命周期的一部分。

`built_in.memory` 是一个更完整的长期记忆子系统。它会给 Agent 注入 `add_memory` 工具，并注册多个 Hook：在输入后检索并注入相关记忆，在新 Session 或压缩前提取长期信息，在达到阈值后清理过期或冲突记忆。

## Quickstart

### 1. 准备环境

- Python 3.10+
- Node.js 和 npm（仅在需要重新构建前端时使用）

### 2. 安装 Python 包

```bash
git clone https://github.com/LILG98/BBagent.git
cd BBagent
pip install -e ".[web]"
```

如果要启用内置长期记忆相关能力，可以安装：

```bash
pip install -e ".[web,memory]"
```

### 3. 构建前端

如果 `frontend/dist` 已存在，可以跳过这一步。否则先构建前端静态文件：

```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. 启动 Web 应用

```bash
python run.py
```

服务默认监听 `http://localhost:8000`，健康检查接口是 `http://localhost:8000/health`。

启动后进入 Settings 配置至少一个模型。OpenAI 兼容、Anthropic、Ollama / vLLM 一类兼容 `/v1/chat/completions` 的服务都可以通过模型配置接入；兼容服务通常需要填写 `baseUrl`、`apiKey` 和实际 `modelName`。

![BBagent onboarding screen](assets/readme/onboarding.png)

### 5. 查看示例模板

仓库提供了一个可导入的 Team 模板：

- [`templates/CodeTeam_template.json`](templates/CodeTeam_template.json)：包含 `Analyst / Architect / Developer / Reviewer / Tester / Documenter` 六个成员的多 Agent 协作示例。

首次启动后端时会自动创建 `data/` 目录。你在 Web Workspace 中创建或导入的 Model、Agent、Team、Skill、MCP、Prompt、Session 和日志会持久化到这里。

## Use Core Library

下面是一个最小的 Python 使用方式：

```python
import asyncio

from bbagent.core.agent import Agent, AgentConfig
from bbagent.core.message import HumanMessage
from bbagent.core.model import AnthropicModel


model = AnthropicModel(
    model="claude-sonnet-4-20250514",
    api_key="sk-ant-xxx",
)

agent = Agent(AgentConfig(
    model=model,
    name="coder",
    system_prompt="You are a helpful coding assistant.",
))


async def main():
    async for event in agent.run(HumanMessage(content="Explain async/await in one sentence.")):
        if event.get("type") == "text":
            print(event["content"], end="", flush=True)


asyncio.run(main())
```

### Add Built-in Tools

```python
from bbagent.built_in_tool import create_coding_tools

tools = await create_coding_tools()
agent.add_tools(list(tools.values()))
```

### Add Built-in Hooks

```python
from bbagent.built_in_hook import HOOK_CREATOR

HOOK_CREATOR["built_in.compress"](agent)
HOOK_CREATOR["built_in.memory"](agent)
```

- `built_in.compress`：在上下文接近模型窗口时压缩旧 Session 内容
- `built_in.memory`：为 Agent 增加长期记忆写入、清理和检索注入能力

### Build a Team

```python
from bbagent.core.team import AgentTeam, TeamConfig

team = AgentTeam.create(TeamConfig(
    name="CodeTeam",
    team_description="A small software delivery team.",
    agents={
        "Architect": architect_agent,
        "Developer": developer_agent,
        "Reviewer": reviewer_agent,
    },
    contacts={
        "Architect": {"Developer": "Implementation owner"},
        "Developer": {
            "Architect": "Technical decision maker",
            "Reviewer": "Code reviewer",
        },
        "Reviewer": {"Developer": "Implementation owner"},
    },
))

await team.start()
await team.push_to_agent("Architect", "Implement a TODO list API.")
```

Team 运行后，成员之间会通过注入的 `send_message` / `broadcast` 工具通信；Web 应用层会把这些事件接到 Team WebSocket 和团队消息记录里。

## Project Layout

```text
BBagent/
├── bbagent/                 # Core Python library
│   ├── core/                # Agent, Team, Message/Session, Tool, Hook, MCP, Skill, Model
│   ├── built_in_tool/       # read/write/edit/bash/grep/find/ls/sub_agent/web_search/fetch_url
│   └── built_in_hook/       # context compression and memory hooks
├── backend/                 # FastAPI app, REST APIs, WebSocket APIs, state factories
├── frontend/                # React + TypeScript + Vite Web Workspace
├── data/                    # Runtime directory, auto-created on first launch
├── doc/                     # Design docs and implementation notes
├── run.py                   # One-command backend launcher
└── pyproject.toml           # Python package metadata
```

## Developer Notes

- [Frontend Design](doc/frontend-design.md)：Web Workspace 的页面结构、组件组织和交互设计。
- [Backend Design](doc/backend-design.md)：FastAPI 后端、状态管理、工厂层和运行时数据目录。
- [API Mapping](doc/api-mapping.md)：前后端 REST / WebSocket API 对照。
- 新增 Tool：参考 [`bbagent/core/tool.py`](bbagent/core/tool.py) 和 [`bbagent/built_in_tool/`](bbagent/built_in_tool/)。
- 新增 Hook：参考 [`bbagent/core/hook.py`](bbagent/core/hook.py) 和 [`bbagent/built_in_hook/`](bbagent/built_in_hook/)。
- 新增 Skill：参考 [`bbagent/core/skill.py`](bbagent/core/skill.py)，Skill 以文件夹式能力包组织 prompt、工具和配置。
- 接入 MCP：参考 [`bbagent/core/mcp.py`](bbagent/core/mcp.py) 和后端 MCP 配置接口。

## License

[MIT](LICENSE) © 2026 [LILG98](https://github.com/LILG98)
