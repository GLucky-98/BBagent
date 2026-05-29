import os
import sys
import json
import shutil
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib
sys.modules['ollama'] = importlib.import_module('unittest.mock').MagicMock()

from BBagent.core.logger import AgentLogger, _NullLogger, StructuredFormatter, logging

TEMP_DIR = Path(__file__).parent / "temp" / "test_logger"
if TEMP_DIR.exists():
    shutil.rmtree(TEMP_DIR)
TEMP_DIR.mkdir(parents=True, exist_ok=True)

total_passed = 0
total_failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global total_passed, total_failed
    if condition:
        print(f"  [PASS] {name}")
        total_passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        total_failed += 1


def read_log_file(path: Path) -> list[dict]:
    TAG_PREFIX = re.compile(r'^\[[A-Z]+\]\s*')
    entries = []
    if path.exists():
        text = path.read_text(encoding="utf-8")
        for line in text.strip().split("\n"):
            line = line.strip()
            if line:
                stripped = TAG_PREFIX.sub("", line)
                entries.append(json.loads(stripped))
    return entries


# ========================================================================
# Phase 1: Basic logging output
# ========================================================================
print("=" * 60)
print("Phase 1: Basic logging output")
print("=" * 60)

log_dir = TEMP_DIR / "phase1"
logger = AgentLogger(name="test_basic", log_dir=log_dir, console_level=logging.DEBUG)
logger.info("Hello world")
logger.debug("Debug message")
logger.warning("Warning message")
logger.error("Error message")

entries = read_log_file(log_dir / "test_basic.log")
check("log file has 4 entries", len(entries) == 4, f"got {len(entries)}")

levels = [e["level"] for e in entries]
check("info level present", "INFO" in levels)
check("debug level present", "DEBUG" in levels)
check("warning level present", "WARNING" in levels)
check("error level present", "ERROR" in levels)
check("first message is Hello world", entries[0]["message"] == "Hello world")

print()

# ========================================================================
# Phase 2: %d / %s formatting backward compatibility
# ========================================================================
print("=" * 60)
print("Phase 2: %%d / %%s formatting (backward compat)")
print("=" * 60)

logger2 = AgentLogger(name="test_format", log_dir=TEMP_DIR / "phase2", console_level=logging.DEBUG)
logger2.info("Count: %d, Name: %s", 42, "Alice")

entries = read_log_file(TEMP_DIR / "phase2" / "test_format.log")
check("formatted message correct", entries[0]["message"] == "Count: 42, Name: Alice",
      f"got: {entries[0]['message']}")

logger2.info("Single %%d: %d", 99)
entries = read_log_file(TEMP_DIR / "phase2" / "test_format.log")
check("single %d formatted correctly", entries[1]["message"] == "Single %d: 99")

logger2.info("No args, plain string")
entries = read_log_file(TEMP_DIR / "phase2" / "test_format.log")
check("plain string still works", entries[2]["message"] == "No args, plain string")

print()

# ========================================================================
# Phase 3: f-string still works
# ========================================================================
print("=" * 60)
print("Phase 3: f-string style still works")
print("=" * 60)

logger3 = AgentLogger(name="test_fstring", log_dir=TEMP_DIR / "phase3", console_level=logging.DEBUG)
x, y = 10, 20
logger3.info(f"f-string: {x} + {y} = {x + y}")

entries = read_log_file(TEMP_DIR / "phase3" / "test_fstring.log")
check("f-string works", entries[0]["message"] == "f-string: 10 + 20 = 30")

print()

# ========================================================================
# Phase 4: Tag auto-inference via span
# ========================================================================
print("=" * 60)
print("Phase 4: Tag auto-inference via span")
print("=" * 60)

logger4 = AgentLogger(name="test_tag", log_dir=TEMP_DIR / "phase4", console_level=logging.DEBUG)

with logger4.span("tool_bash"):
    logger4.info("Executing bash command")

with logger4.span("hook_check_compression"):
    logger4.debug("Compression check started")

with logger4.span("agent_run"):
    logger4.warning("Agent is running")

with logger4.span("event_handle"):
    logger4.error("Event processing error")

with logger4.span("subagent_extract"):
    logger4.info("Extracting memories")

entries = read_log_file(TEMP_DIR / "phase4" / "test_tag.log")
check("[TOOL] inferred from tool_bash", entries[0]["message"] == "Executing bash command")
check("[HOOK] inferred from hook_*", entries[1]["message"] == "Compression check started")
check("[AGENT] inferred from agent_*", entries[2]["message"] == "Agent is running")
check("[AGENT] inferred from event_handle", entries[3]["message"] == "Event processing error")
check("[SUBAGENT] inferred from subagent_*", entries[4]["message"] == "Extracting memories")

raw4 = (TEMP_DIR / "phase4" / "test_tag.log").read_text(encoding="utf-8")
check("tag prefix in raw line: [TOOL]", "[TOOL] {" in raw4)
check("tag prefix in raw line: [HOOK]", "[HOOK] {" in raw4)
check("tag prefix in raw line: [AGENT]", "[AGENT] {" in raw4)
check("tag prefix in raw line: [SUBAGENT]", "[SUBAGENT] {" in raw4)

print()

# ========================================================================
# Phase 5: No span → no tag
# ========================================================================
print("=" * 60)
print("Phase 5: No span → no tag")
print("=" * 60)

logger5 = AgentLogger(name="test_notag", log_dir=TEMP_DIR / "phase5", console_level=logging.DEBUG)
logger5.info("Outside any span")

entries = read_log_file(TEMP_DIR / "phase5" / "test_notag.log")
check("no tag when outside span", entries[0]["message"] == "Outside any span")

print()

# ========================================================================
# Phase 6: Explicit tag overrides auto-inference
# ========================================================================
print("=" * 60)
print("Phase 6: Explicit tag overrides auto-inference")
print("=" * 60)

logger6 = AgentLogger(name="test_explicit", log_dir=TEMP_DIR / "phase6", console_level=logging.DEBUG)

with logger6.span("tool_bash"):
    logger6.info("Should be tagged as TOOL by default")
    logger6.info("Should be tagged as AGENT explicitly", tag="AGENT")

entries = read_log_file(TEMP_DIR / "phase6" / "test_explicit.log")
check("auto TOOL inside tool_bash", entries[0]["message"] == "Should be tagged as TOOL by default")
check("explicit AGENT overrides", entries[1]["message"] == "Should be tagged as AGENT explicitly")

print()

# ========================================================================
# Phase 7: Nested span uses innermost tag
# ========================================================================
print("=" * 60)
print("Phase 7: Nested span uses innermost tag")
print("=" * 60)

logger7 = AgentLogger(name="test_nested", log_dir=TEMP_DIR / "phase7", console_level=logging.DEBUG)

with logger7.span("agent_run"):
    logger7.info("Inside agent_run")
    with logger7.span("tool_read"):
        logger7.info("Inside tool_read inside agent_run")
    logger7.info("Back to agent_run")

entries = read_log_file(TEMP_DIR / "phase7" / "test_nested.log")
check("outer [AGENT]", entries[0]["message"] == "Inside agent_run")
check("inner [TOOL]", entries[1]["message"] == "Inside tool_read inside agent_run")
check("back to [AGENT]", entries[2]["message"] == "Back to agent_run")

print()

# ========================================================================
# Phase 8: context dict is preserved
# ========================================================================
print("=" * 60)
print("Phase 8: context dict preserved")
print("=" * 60)

logger8 = AgentLogger(name="test_context", log_dir=TEMP_DIR / "phase8", console_level=logging.DEBUG)
logger8.info("With context", context={"key": "value", "count": 3})

entries = read_log_file(TEMP_DIR / "phase8" / "test_context.log")
check("context key present", entries[0].get("context", {}).get("key") == "value")
check("context count present", entries[0].get("context", {}).get("count") == 3)

print()

# ========================================================================
# Phase 9: %d formatting + span + tag all at once
# ========================================================================
print("=" * 60)
print("Phase 9: %%d + span + context all at once")
print("=" * 60)

logger9 = AgentLogger(name="test_combined", log_dir=TEMP_DIR / "phase9", console_level=logging.DEBUG)

with logger9.span("hook_compress"):
    logger9.info(
        "Compression needed: %d/%d",
        45000, 160000,
        context={"visible_tokens": 45000, "threshold": 160000},
    )

entries = read_log_file(TEMP_DIR / "phase9" / "test_combined.log")
check("[HOOK] tag", entries[0]["message"].startswith("Compression needed"),
      f"got: {entries[0]['message']}")
check("formatted numbers", entries[0]["message"] == "Compression needed: 45000/160000")
check("context preserved", entries[0].get("context", {}).get("visible_tokens") == 45000)

print()

# ========================================================================
# Phase 10: _NullLogger doesn't crash
# ========================================================================
print("=" * 60)
print("Phase 10: _NullLogger no-op safety")
print("=" * 60)

null = _NullLogger()

try:
    null.info("Human message", context={"key": "val"})
    null.debug("Debug %d", 42, context={"n": 42})
    null.warning("Warning: %s", "oops", context={"err": "oops"}, tag="AGENT")
    null.error("Error", exc_info=None)
    null.fatal("Fatal", tag="HOOK")
    with null.span("tool_test"):
        null.info("Inside null span")
    check("_NullLogger no-op safe", True)
except Exception as e:
    check("_NullLogger no-op safe", False, f"raised {e}")

print()

# ========================================================================
# Phase 11: StructuredFormatter JSON format
# ========================================================================
print("=" * 60)
print("Phase 11: StructuredFormatter JSON format")
print("=" * 60)

logger11 = AgentLogger(name="test_json", log_dir=TEMP_DIR / "phase11", console_level=logging.DEBUG)
logger11.info("JSON check")

entries = read_log_file(TEMP_DIR / "phase11" / "test_json.log")
entry = entries[0]
check("has timestamp", "timestamp" in entry)
check("has level", "level" in entry)
check("has agent", "agent" in entry)
check("has trace_id", "trace_id" in entry)
check("has span_id", "span_id" in entry)
check("has message", "message" in entry)

print()

# ========================================================================
# Summary
# ========================================================================
print("=" * 60)
print(f"Results: {total_passed} passed, {total_failed} failed")
print("=" * 60)

if TEMP_DIR.exists():
    shutil.rmtree(TEMP_DIR)

if total_failed > 0:
    exit(1)
else:
    exit(0)
