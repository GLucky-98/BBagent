# BBagent Baseline Test Suite

This document defines the repository's baseline tests: fast, deterministic checks that should continue to pass after feature work, refactors, and internal rewrites.

## Goals

- Protect stable behavior and public contracts rather than implementation details.
- Keep the default suite offline: no real LLM calls, no external MCP servers, no network services.
- Use temporary directories for filesystem work so tests do not touch local `data/` or user files.
- Make failures point to a module contract: message/session, tool invocation, team communication, built-in tools, template compatibility.

## Current Coverage

The initial suite lives under `tests/` and covers:

### Core (`tests/unit/core/`)

- `test_message.py`
  - content block and model message round trips
  - session create/save/load
  - incomplete turn merge behavior
  - session fork independence
- `test_tool.py`
  - schema generation from Python signatures
  - argument validation and coercion
  - Pydantic model parameters
  - async tool invocation contract
- `test_team.py`
  - contact-based team tool injection
  - direct messages and contact rejection
  - broadcast accounting
  - team message serialization
- `test_skill.py`
  - skill loading and prompt generation
- `test_mcp_tool.py`
  - MCP tool ID derivation (uuid5)
  - MCP tool func_name format (`mcp:{server}::{raw}`)
- `test_agent_interrupt.py`
  - agent interrupt during execution
  - interrupt state transitions

### Built-in Tools (`tests/unit/built_in_tool/`)

- `test_file_tools.py`
  - read/write/edit behavior under `Policy.cwd`
  - binary-file rejection
  - grep/find/ls expected output
- `test_web_tools.py`
  - web tool schema and invocation contracts

### Built-in Hooks (`tests/unit/built_in_hook/`)

- `test_memory_optimization.py`
  - memory hook optimization behavior
- `test_todo_subsystem.py`
  - todo subsystem hook behavior

### Backend (`tests/unit/backend/`)

- `test_agent_factory_messages.py`
  - agent factory message handling
- `test_agent_factory_policy.py`
  - agent factory policy construction and updates
- `test_dispatcher.py`
  - AgentOutputDispatcher fan-out behavior
  - round buffer and replay mechanism
  - sentinel-based queue switching
- `test_session_factory.py`
  - SessionManager index building
  - session listing and filtering
  - session fork at turn
  - session deletion
  - LRU cache behavior
- `test_skill_factory.py`
  - skill factory CRUD operations
- `test_team_factory.py`
  - team factory creation and member management

### Integration (`tests/integration/`)

- `test_template_codeteam.py`
  - `templates/CodeTeam_template.json` shape
  - template compatibility with core `AgentTeam`

## Running Tests

Install development dependencies first:

```bash
pip install -e ".[dev,web]"
```

Run the baseline Python suite:

```bash
python -m pytest tests
```

Run by layer:

```bash
python -m pytest tests/unit
python -m pytest tests/unit/core
python -m pytest tests/unit/backend
python -m pytest tests/unit/built_in_tool
python -m pytest tests/unit/built_in_hook
python -m pytest tests/integration
```

Run a focused test:

```bash
python -m pytest tests/unit/backend/test_dispatcher.py
```

Run quality gates:

```bash
ruff check .
mypy bbagent backend
```

For frontend regression gates:

```bash
cd frontend
npm run lint
npm run build
```

## What Belongs In Baseline Tests

Add baseline tests when a behavior should remain true across refactors:

- serialization formats that persisted sessions/configs depend on
- Tool input schema and invocation semantics
- built-in tool behavior visible to agents
- Team message routing and visibility rules
- API payload shapes consumed by the frontend
- bundled templates and backward-compatible config loading
- Factory CRUD contracts (model, agent, team, skill, session)
- Dispatcher fan-out and replay behavior
- Unified ID derivation (builtin tool UUID, MCP tool uuid5)

Avoid baseline tests for:

- exact wording of non-contractual log messages
- real model output quality
- timing-sensitive async behavior unless controlled with fakes
- incidental ordering unless the product contract requires it

## Test Design Rules

- Use fake models for agent tests. Real LLM calls are not baseline tests.
- Use `tmp_path` for all filesystem state.
- Prefer assertions on durable outcomes: files written, messages persisted, tool results, structured dicts.
- Keep tests small and named after the behavior they protect.
- If a regression is discovered manually, add a failing test first, then fix the behavior.

## Suggested Next Additions

- FastAPI `TestClient` tests for `/health` and CRUD endpoints with an isolated state manager.
- Hook lifecycle tests using a fake hook and fake model.
- Frontend Vitest coverage for `frontend/src/lib/api.ts` and Zustand store behavior.
- Playwright smoke test for the workspace once the backend can run with isolated fixtures.
- Team conversation factory tests (create, load, delete conversations).
- File watch WebSocket handler tests with mock filesystem events.
