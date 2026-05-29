# BBagent Testing Plan

## 1. Overview

This document describes the comprehensive testing strategy for the BBagent repository. The testing framework is designed to be modular, maintainable, and resilient to source code changes, allowing incremental updates rather than wholesale rewrites.

## 2. Design Principles

### 2.1 Framework Philosophy
- **No pytest/framework**: Pure Python scripts with simple test runners
- **Environment isolation**: All environment variables loaded from `.env` via centralized `env.py`
- **Module isolation**: Tests organized by functional area (unit/integration/builtin)
- **No hardcoded secrets**: API keys loaded at runtime, never written in test code

### 2.2 Change Tolerance
When source code changes:
- Only the affected test file needs updating
- Test structure (naming, runner) remains stable
- New modules can be added by creating new test files following the same pattern
- No central test registry to maintain

## 3. Directory Structure

```
test/
├── run_tests.py              # Test entry point and runner
├── conftest.py               # Test environment configuration
├── env.py                    # Environment variable loader (from .env)
│
├── unit/                     # Unit tests (single component)
│   ├── test_model.py         # Model component
│   ├── test_tool.py           # Tool component
│   ├── test_message.py        # Message component
│   ├── test_hook.py           # Hook component
│   ├── test_session.py        # Session component
│   ├── test_logger.py         # Logger component
│   ├── test_skill.py          # Skill component
│   └── test_input.py          # Input component
│
├── integration/              # Integration tests (multi-component)
│   ├── test_agent_basic.py    # Agent basic functionality
│   ├── test_agent_tools.py    # Agent tool calling
│   ├── test_agent_stream.py   # Agent streaming output
│   ├── test_agent_skill.py    # Agent skill invocation
│   ├── test_agent_mcp.py      # Agent MCP tool calling
│   ├── test_subagent.py       # SubAgent functionality
│   └── test_team.py           # Multi-agent collaboration
│
├── builtin/                  # Built-in tool/hook tests
│   ├── test_read_tool.py      # read tool
│   ├── test_write_tool.py     # write tool
│   ├── test_edit_tool.py      # edit tool
│   ├── test_bash_tool.py      # bash tool
│   ├── test_grep_tool.py      # grep tool
│   ├── test_find_tool.py      # find tool
│   ├── test_ls_tool.py        # ls tool
│   ├── test_memory.py         # Memory system
│   └── test_ctx_compress.py   # Context compression
│
└── scripts/                   # Test utilities
    └── gen_test_data.py       # Generate test data files
```

## 4. Environment Configuration

### 4.1 env.py
```python
"""
Environment loader for tests.
Loads variables from .env file in project root.
"""
from dotenv import load_dotenv
from pathlib import Path
import os

def get_env():
    load_dotenv(Path(__file__).parent.parent / ".env")
    return {
        "model": os.getenv("MODEL"),
        "api_key": os.getenv("API_KEY"),
        "base_url": os.getenv("ANTHROPIC_BASE_URL"),
        "openai_base_url": os.getenv("OPENAI_BASE_URL"),
    }
```
All test files import from this module to get runtime configuration.

### 4.2 .env Requirements
```
MODEL=MiniMax-M2.7
API_KEY=your_key_here
ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic
OPENAI_BASE_URL=https://api.minimaxi.com/v1
```

## 5. Test File Template

All test files follow this pattern:

```python
#!/usr/bin/env python3
"""
test_<module>.py - <Description>

Test for <module_name> component.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from env import get_env
ENV = get_env()

# ============ Test Cases ============

def test_case_1():
    """Description of what this test verifies."""
    print("[TEST] case_1: description")
    try:
        # setup
        # action
        # assert
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False

# ============ Main Runner ============

def main():
    tests = [
        # List all test functions
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0

if __name__ == "__main__":
    sys.exit(0 if main() else 1)
```

## 6. Test Entry Point

### 6.1 run_tests.py
The main runner supports selective execution:
- No args: run all tests
- `unit`: unit tests only
- `integration`: integration tests only
- `builtin`: builtin tool/hook tests only
- `test_<name>`: specific test file

## 7. Test Specifications

### 7.1 Unit Tests

#### test_model.py
- Model initialization with env config
- Payload construction for API calls
- Response parsing (text, tool_calls, errors)
- Model invocation (sync/async/stream)
- Error handling (rate limits, timeouts)

#### test_tool.py
- Tool creation via `@tool` decorator
- Tool invocation with parameters
- Stateful vs stateless tools
- Tool schema validation

#### test_message.py
- Message type creation (Human/Model/Tool)
- Content block types (Text/Image/ToolUse)
- Turn management and sequencing
- Session message addition
- Token estimation

#### test_hook.py
- Hook registration and priority
- Hook trigger at specified points
- HookContext data passing
- Break loop functionality
- Hook merging/composition

#### test_session.py
- Session creation and initialization
- Message appending and retrieval
- Session fork (branching)
- Visible context calculation
- Turn summarization flags

#### test_logger.py
- Logger initialization
- Structured JSON output
- Span/trace tracking
- Context propagation
- File rotation

#### test_skill.py
- SKILL.md parsing
- scan_skills from disk
- Skill metadata extraction

#### test_input.py
- Event creation
- InputChannel push/pop
- Timer scheduling
- Event type handling

### 7.2 Integration Tests

#### test_agent_basic.py
- Agent initialization with config
- Single-turn conversation
- Multi-turn conversation
- Agent state transitions
- Error recovery

#### test_agent_tools.py
- Tool registration with agent
- Tool call execution
- Tool result handling
- Multi-tool sequences
- Tool call errors

#### test_agent_stream.py
- Streaming response handling
- Chunk type differentiation
- Text chunk accumulation
- Thinking chunk handling
- Tool use chunk handling

#### test_agent_skill.py
- Skill loading into agent
- Skill invocation via message
- Skill result handling
- Multiple skill management
- Skill error handling

#### test_agent_mcp.py
- MCP client connection
- MCP tool listing
- MCP tool invocation
- MCP tool result handling
- MCP server lifecycle

#### test_subagent.py
- SubAgent creation
- Context compression execution
- Summarization quality
- Session state after compression

#### test_team.py
- AgentTeam creation
- Agent registration
- Inter-agent messaging
- Broadcast functionality
- Team tool injection

### 7.3 Built-in Tool/Hook Tests

#### test_read_tool.py
- Basic file reading
- Offset and limit parameters
- Truncation for large files
- Binary vs text handling
- Non-existent file error

#### test_write_tool.py
- File creation
- Directory creation
- Content overwrite
- Binary content
- Permission error handling

#### test_edit_tool.py
- Single replacement
- Multiple replacements
- Regex replacement
- No match handling
- File creation from edit

#### test_bash_tool.py
- Simple command execution
- Working directory
- Environment variables
- Timeout handling
- Exit code processing

#### test_grep_tool.py
- Basic text search
- Regex pattern matching
- Case sensitivity
- Multiple file search
- No match handling

#### test_find_tool.py
- File name patterns
- Directory traversal
- Depth limiting
- Permission handling
- Symlink handling

#### test_ls_tool.py
- Directory listing
- Format output
- Hidden files
- Recursive listing
- Permission errors

#### test_memory.py
- MemoryManager initialization
- Memory addition
- Vector search
- BM25 search
- Hybrid search (RRF fusion)
- Memory deletion

#### test_ctx_compress.py
- Turn grouping by size
- Compression trigger threshold
- Summarization execution
- Compressed turn replacement
- Token count after compression

## 8. Test Data Management

### 8.1 Temporary Files
- All test data stored in `test/temp/`
- Files preserved after test completion (per CLAUDE.md)
- Cleanup only via manual intervention if needed

### 8.2 Test Data Generation
Use `scripts/gen_test_data.py` to create:
- Sample text files for read/edit/grep tests
- Sample directories for find/ls tests
- Mock session data for compression tests

## 9. Running Tests

### 9.1 Run All Tests
```bash
python test/run_tests.py
```

### 9.2 Run by Category
```bash
python test/run_tests.py unit
python test/run_tests.py integration
python test/run_tests.py builtin
```

### 9.3 Run Specific Module
```bash
python test/run_tests.py test_model
python test/run_tests.py test_agent_basic
```

### 9.4 Run Single File
```bash
python test/unit/test_model.py
```

## 10. Success Criteria

- All test files execute without import errors
- Each test function produces clear PASS/FAIL output
- Test files remain functional when source modules are updated
- New modules can be tested by creating new files following this template

## 11. Maintenance

When source code changes:
1. Identify affected test file(s)
2. Update test cases to match new interfaces
3. Add new test cases for new functionality
4. Do not modify the test runner or template structure
5. Document interface changes in test file header comments

## 12. Coverage Goals

### Core Components (BBagent/core/)
- Agent: Basic flow, tools, streaming, skills, MCP
- Model: Initialization, invocation, response handling
- Tool: Creation, registry, invocation
- Message: All message types, session, turn
- Hook: Registration, triggering, context
- Session: Creation, fork, token count
- Logger: Output, formatting, spans
- Skill: Loading, parsing, management
- Input: Events, channel operations
- Team: Agent registration, messaging

### Built-in Components (BBagent/built_in_*/)
- All built-in tools: read, write, edit, bash, grep, find, ls
- Memory system: Manager, hooks, search
- Context compression: Hook, execution

## 13. Model Configuration

All tests using models must:
1. Import `from env import get_env`
2. Use `ENV = get_env()` to get configuration
3. Initialize models with env values:
```python
model = AnthropicModel(
    model=ENV["model"],
    api_key=ENV["api_key"],
    base_url=ENV["base_url"]
)
```

Never hardcode API keys or model names in test files.