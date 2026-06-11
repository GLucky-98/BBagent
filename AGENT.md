# AGENT Guide for BBagent

This file is the working guide for coding agents and maintainers changing this repository. It focuses on safe development flow, test expectations, and project-specific contracts.

## Project Map

- `bbagent/`: core agent framework.
  - `core/`: Agent, Team, Session, Tool, Model, Hook, MCP, Skill primitives.
  - `built_in_tool/`: built-in coding tools such as read, write, edit, bash, grep, find, ls, sub_agent.
  - `built_in_hook/`: built-in lifecycle extensions, including context compression and memory.
- `backend/`: FastAPI app, API routers, state coordinator, factories, schemas, dispatchers.
- `frontend/`: Vite + React workspace UI.
- `templates/`: importable team templates. `CodeTeam_template.json` is a compatibility fixture.
- `tests/`: baseline pytest suite.
- `doc/testing-baseline.md`: baseline test philosophy and current coverage.

## Development Principles

- Keep the core library usable without the web UI.
- Keep baseline tests offline and deterministic. Do not call real LLMs, MCP servers, or external APIs in default tests.
- Prefer fake models, temporary directories, and local fixtures.
- Protect persisted formats: sessions, team messages, templates, and frontend-facing schemas are compatibility surfaces.
- Keep changes scoped. Avoid drive-by refactors across core, backend, and frontend unless the behavior requires it.
- Do not write tests against incidental wording unless the text is part of a user-facing or agent-facing contract.

## Complete Development Test Flow

Use the narrowest useful test while iterating, then run the full relevant gate before handing off.

### 1. Python Baseline Tests

Run all baseline tests:

```bash
python -m pytest tests
```

Run by layer:

```bash
python -m pytest tests/unit
python -m pytest tests/integration
```

Run a focused test while developing:

```bash
python -m pytest tests/unit/core/test_tool.py
```

### 2. Python Quality Gates

Run lint:

```bash
ruff check .
```

Run type checks:

```bash
mypy bbagent backend
```

If a change only touches tests, at least run:

```bash
ruff check tests
python -m pytest tests
```

### 3. Frontend Gates

For frontend changes:

```bash
cd frontend
npm run lint
npm run build
```

If frontend tests are added later, include them in this section and in `frontend/package.json`.

### 4. Full-Stack Smoke Check

Use this when changing API payloads, factories, sessions, team runtime, websocket behavior, or frontend integration:

```bash
cd frontend
npm run build
cd ..
python run.py
```

Then verify:

- `GET /health` returns `{"status": "ok"}`.
- The web UI loads.
- Existing model, agent, team, prompt, skill, MCP, and session screens still render.
- A team template can still be imported or represented by the backend.

### 5. Suggested Verification Matrix

- Core message/session/tool/team change:
  - `python -m pytest tests/unit/core`
  - `python -m pytest tests/integration/test_template_codeteam.py`
  - `ruff check bbagent tests`
- Built-in tool change:
  - `python -m pytest tests/unit/built_in_tool`
  - add or update tests for the tool behavior
  - `ruff check bbagent/built_in_tool tests`
- Backend API/factory/schema change:
  - `python -m pytest tests`
  - `ruff check backend bbagent tests`
  - `mypy bbagent backend`
  - frontend `npm run build` if payload shapes changed
- Frontend component/store/API change:
  - `cd frontend && npm run lint && npm run build`
  - run Python tests if API contracts changed
- Template/config compatibility change:
  - `python -m pytest tests/integration/test_template_codeteam.py`
  - add fixture coverage for new persistent config formats
- Memory hook change:
  - install `.[memory]` if needed
  - add fake or local-store tests instead of relying on live embedding/model services

## Baseline Test Policy

The current baseline suite is documented in `doc/testing-baseline.md`.

When adding behavior that should survive refactors, add a test under `tests/` in the same change. Good baseline targets include:

- session serialization and visible context behavior
- tool schemas and invocation semantics
- built-in tool filesystem behavior
- team routing and message persistence
- backend schema and factory persistence contracts
- template loading and backward compatibility

Tests should avoid:

- live LLM calls
- network-only services
- depending on a developer's local `data/` directory
- hidden global state that makes test order matter

## Data and Persistence Notes

- Runtime app data is stored under `data/`, created by `backend.state`.
- Tests should use `tmp_path` or isolated fixtures, not the real `data/` directory.
- Session files are persisted as `.jsonl` plus `.md` metadata; treat both as compatibility surfaces.
- Team messages are persisted as JSONL. Keep message shape stable unless migration is planned.
- Templates in `templates/` are public examples and compatibility fixtures.

## Frontend Notes

- The UI is built with React, Vite, Zustand, Radix UI, Tailwind, and lucide icons.
- `frontend/src/lib/api.ts` is the main backend contract surface.
- `frontend/src/types/index.ts` should stay aligned with `backend/schemas.py`.
- After schema changes, verify both TypeScript build and the corresponding backend tests.

## Agent-Specific Working Rules

- Inspect existing patterns before editing.
- Preserve unrelated user changes. The worktree may already be dirty.
- Prefer small, behavior-focused tests over large snapshots.
- Use `tmp_path` for files created by tests.
- If a command fails because dependencies are missing, install only the dependency group needed for the verification.
- Report skipped checks clearly, including why they were skipped.
- Before finishing, state which tests and quality gates were run.
