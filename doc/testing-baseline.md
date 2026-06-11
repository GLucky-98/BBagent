# BBagent Baseline Test Suite

This document defines the repository's baseline tests: fast, deterministic checks that should continue to pass after feature work, refactors, and internal rewrites.

## Goals

- Protect stable behavior and public contracts rather than implementation details.
- Keep the default suite offline: no real LLM calls, no external MCP servers, no network services.
- Use temporary directories for filesystem work so tests do not touch local `data/` or user files.
- Make failures point to a module contract: message/session, tool invocation, team communication, built-in tools, template compatibility.

## Current Coverage

The initial suite lives under `tests/` and covers:

- `tests/unit/core/test_message.py`
  - content block and model message round trips
  - session create/save/load
  - incomplete turn merge behavior
  - session fork independence
- `tests/unit/core/test_tool.py`
  - schema generation from Python signatures
  - argument validation and coercion
  - Pydantic model parameters
  - async tool invocation contract
- `tests/unit/core/test_team.py`
  - contact-based team tool injection
  - direct messages and contact rejection
  - broadcast accounting
  - team message serialization
- `tests/unit/built_in_tool/test_file_tools.py`
  - read/write/edit behavior under `Policy.cwd`
  - binary-file rejection
  - grep/find/ls expected output
- `tests/integration/test_template_codeteam.py`
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
python -m pytest tests/integration
```

Run quality gates:

```bash
ruff check .
mypy bbagent backend
```

For frontend regression gates, use the existing scripts:

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
- Factory tests for model, prompt, skill, agent, and team config persistence.
- Hook lifecycle tests using a fake hook and fake model.
- Frontend Vitest coverage for `frontend/src/lib/api.ts` and Zustand store behavior.
- Playwright smoke test for the workspace once the backend can run with isolated fixtures.
