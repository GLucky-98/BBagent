import os
import sys
import json
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import importlib
sys.modules['ollama'] = importlib.import_module('unittest.mock').MagicMock()

from BBagent.core.message import (
    Session, Turn,
    HumanMessage, ModelMessage, ToolMessage,
    ToolUseBlock,
)

tmp = './tmp/test_session'
if os.path.exists(tmp):
    shutil.rmtree(tmp)

print("=" * 60)
print("Phase 1: Create session and verify initial state")
print("=" * 60)

session = Session.create(tmp)
session_dir = session.dir

print(f"Session id: {session.id}")
print(f"Session dir: {session.dir}")
print(f"Session timestamp: {session.timestamp}")
print(f"Initial turn_count: {session.turn_count}")
print(f"Initial messages count: {len(session.messages)}")
print(f"window_start: {session.window_start}")
print(f"compress_turn_count: {session.compress_turn_count}")
print(f"total_input_cost_tokens: {session.total_input_cost_tokens}")
print(f"total_output_cost_tokens: {session.total_output_cost_tokens}")

assert session.turn_count == 0
assert len(session.messages) == 0
assert session.window_start == 0
assert session.compress_turn_count == 0
print()

print("=" * 60)
print("Phase 2: Add complete turns and verify structure")
print("=" * 60)

session.add_message(HumanMessage(content='Hello, how are you?'))
session.add_message(ModelMessage(
    id='msg-1', content='I am doing well!', stop_reason='end_turn',
    usage_data={'input_tokens': 10, 'output_tokens': 5},
    input_tokens=10, output_tokens=5,
))
session.add_message(HumanMessage(content='Tell me about Python.'))
session.add_message(ModelMessage(
    id='msg-2', content='Python is a versatile programming language...',
    stop_reason='end_turn', usage_data={},
    input_tokens=50, output_tokens=100,
))
session.add_message(HumanMessage(content='How about Rust?'))
session.add_message(ModelMessage(
    id='msg-3', content='Rust is a systems programming language...',
    stop_reason='end_turn', usage_data={},
    input_tokens=80, output_tokens=120,
))

print(f"Turn count: {session.turn_count}")
print(f"Messages count: {len(session.messages)}")

assert session.turn_count == 3
assert len(session.messages) == 6

for i in range(3):
    turn = session.get_turn(i)
    assert turn.is_complete, f"Turn {i} should be complete"
    assert isinstance(turn.messages[0], HumanMessage), f"Turn {i} first msg should be HumanMessage"
    assert isinstance(turn.messages[-1], ModelMessage), f"Turn {i} last msg should be ModelMessage"
    assert turn.messages[-1].stop_reason == 'end_turn', f"Turn {i} should end with end_turn"
    print(f"  Turn {i}: complete={turn.is_complete}, "
          f"messages={len(turn.messages)}, "
          f"tokens={turn.input_tokens}+{turn.output_tokens}")

print(f"total_input_cost_tokens: {session.total_input_cost_tokens}")
print(f"total_output_cost_tokens: {session.total_output_cost_tokens}")
assert session.total_input_cost_tokens == 140  # 10 + 50 + 80
assert session.total_output_cost_tokens == 225  # 5 + 100 + 120
print()

print("=" * 60)
print("Phase 3: Turn management - incomplete turn dropped on new HumanMessage")
print("=" * 60)

session.add_message(HumanMessage(content='Compare Python and Rust.'))
session.add_message(ModelMessage(
    id='msg-4', content='Python is great for...', stop_reason='tool_use',
    usage_data={}, input_tokens=30, output_tokens=20,
))

print(f"After tool_use - turn_count: {session.turn_count}")
assert session.turn_count == 4, f"Expected 4 turns, got {session.turn_count}"
assert not session.get_turn(-1).is_complete, "Turn 3 should be incomplete"

session.add_message(HumanMessage(content='Actually, forget it. Tell me about Go.'))

print(f"After 'forget it' - turn_count: {session.turn_count}")
assert session.turn_count == 4, f"Incomplete turn should be dropped, so still 4 turns"
assert len(session.get_turn(-1).messages) == 1, "New turn should only have HumanMessage"
assert session.get_turn(-1).messages[0].content == 'Actually, forget it. Tell me about Go.'

session.add_message(ModelMessage(
    id='msg-5', content='Go is a statically typed language...',
    stop_reason='end_turn', usage_data={},
    input_tokens=20, output_tokens=40,
))
assert session.turn_count == 4
assert session.get_turn(-1).is_complete
print("  Incomplete turn correctly dropped on new HumanMessage")
print()

print("=" * 60)
print("Phase 4: get_turn() negative indexing and edge cases")
print("=" * 60)

last_turn = session.get_turn(-1)
assert last_turn.messages[-1].content == 'Go is a statically typed language...'
print(f"  get_turn(-1) content: {last_turn.messages[0].content}")

first_turn = session.get_turn(0)
assert first_turn.messages[0].content == 'Hello, how are you?'
print(f"  get_turn(0) content: {first_turn.messages[0].content}")

try:
    session.get_turn(100)
    assert False, "Should have raised IndexError"
except IndexError:
    print("  get_turn(100) correctly raises IndexError")

try:
    session.get_turn(-100)
    assert False, "Should have raised IndexError"
except IndexError:
    print("  get_turn(-100) correctly raises IndexError")

try:
    empty_session = Session(id='empty', dir=tmp)
    empty_session.get_turn(0)
    assert False, "Should have raised IndexError"
except IndexError:
    print("  get_turn(0) on empty session correctly raises IndexError")
print()

print("=" * 60)
print("Phase 5: get_visible_token_count()")
print("=" * 60)

token_count = session.get_visible_token_count()
print(f"  get_visible_token_count() = {token_count}")
assert token_count > 0, "Token count should be positive"

all_tokens = sum(t.token_count for t in session.turns if t.is_complete)
assert token_count == all_tokens, \
    f"Expected total {all_tokens}, got {token_count}"
print(f"  All complete turns total token count: {all_tokens}")
print()

print("=" * 60)
print("Phase 6: ever_used_tools aggregation with ToolMessage")
print("=" * 60)

tool_session = Session.create(tmp + '_tools')
tool_session.add_message(HumanMessage(content='Run some tools'))
tool_session.add_message(ModelMessage(
    id='msg-t1', content='', stop_reason='tool_use',
    usage_data={}, input_tokens=10, output_tokens=5,
))
tool_session.add_message(ToolMessage(
    id='call_1', name='bash', content='ls -la output',
))
tool_session.add_message(ToolMessage(
    id='call_2', name='read_file', content='file content',
))
tool_session.add_message(ModelMessage(
    id='msg-t2', content='Done.', stop_reason='end_turn',
    usage_data={}, input_tokens=20, output_tokens=5,
))

turn = tool_session.get_turn(0)
print(f"  Turn ever_used_tools: {turn.ever_used_tools}")
assert 'bash' in turn.ever_used_tools
assert 'read_file' in turn.ever_used_tools
assert len(turn.ever_used_tools) == 2

print(f"  Session ever_used_tools: {tool_session.ever_used_tools}")
assert 'bash' in tool_session.ever_used_tools
assert 'read_file' in tool_session.ever_used_tools

tool_session.save()
loaded_tools = Session.load(tool_session.id, tool_session.dir)
assert 'bash' in loaded_tools.ever_used_tools
assert 'read_file' in loaded_tools.ever_used_tools
print("  ever_used_tools persisted correctly")
print()

print("=" * 60)
print("Phase 7: fork()")
print("=" * 60)

forked = session.fork()
print(f"  Fork id: {forked.id}")
print(f"  Fork dir: {forked.dir}")
print(f"  Fork turn_count: {forked.turn_count}")
print(f"  Fork messages count: {len(forked.messages)}")

assert forked.id != session.id
assert forked.id.startswith(session.id + '_fork_')
assert forked.dir != session.dir
assert str(forked.dir).startswith(str(session.dir))
assert 'fork' in str(forked.dir)
assert forked.turn_count == session.turn_count
assert len(forked.messages) == len(session.messages)
assert forked.window_start == session.window_start
assert forked.compress_turn_count == session.compress_turn_count
assert forked.total_input_cost_tokens == session.total_input_cost_tokens
assert forked.total_output_cost_tokens == session.total_output_cost_tokens

forked_turn = forked.get_turn(0)
orig_turn = session.get_turn(0)
assert forked_turn.messages[0].content == orig_turn.messages[0].content
assert forked_turn.input_tokens == orig_turn.input_tokens
assert forked_turn.output_tokens == orig_turn.output_tokens
assert forked_turn.ever_used_tools == orig_turn.ever_used_tools

assert forked.messages[0] is not session.messages[0], \
    "Fork should deep copy, not share references"

forked_loaded = Session.load(forked.id, forked.dir)
assert forked_loaded.turn_count == forked.turn_count
assert len(forked_loaded.messages) == len(forked.messages)
print("  Fork verified (deep copy + persistence)")
print()

print("=" * 60)
print("Phase 8: Save and Load roundtrip")
print("=" * 60)

session.save()
loaded = Session.load(session.id, session_dir)

print(f"  Loaded turn_count: {loaded.turn_count}")
print(f"  Loaded messages count: {len(loaded.messages)}")

assert loaded.turn_count == session.turn_count
assert len(loaded.messages) == len(session.messages)
assert loaded.total_input_cost_tokens == session.total_input_cost_tokens
assert loaded.total_output_cost_tokens == session.total_output_cost_tokens
assert loaded.compress_turn_count == session.compress_turn_count
assert loaded.window_start == session.window_start

for i in range(loaded.turn_count):
    orig_turn = session.get_turn(i)
    loaded_turn = loaded.get_turn(i)
    assert len(loaded_turn.messages) == len(orig_turn.messages)
    for j in range(len(orig_turn.messages)):
        assert orig_turn.messages[j].content == loaded_turn.messages[j].content
    assert loaded_turn.is_complete == orig_turn.is_complete
    assert loaded_turn.input_tokens == orig_turn.input_tokens
    assert loaded_turn.output_tokens == orig_turn.output_tokens
    assert loaded_turn.start_timestamp == orig_turn.start_timestamp
    if orig_turn.end_timestamp:
        assert loaded_turn.end_timestamp == orig_turn.end_timestamp

print("  All turns and messages correctly restored")
print()

print("=" * 60)
print("Phase 9: JSONL only contains completed turns")
print("=" * 60)

jsonl_path = os.path.join(str(session_dir), session.id + '.jsonl')
jsonl_lines = []
with open(jsonl_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line:
            jsonl_lines.append(json.loads(line))

total_msgs_in_complete_turns = sum(
    len(turn.messages) for turn in session.turns if turn.is_complete
)
print(f"  JSONL lines: {len(jsonl_lines)}")
print(f"  Messages in complete turns: {total_msgs_in_complete_turns}")
assert len(jsonl_lines) == total_msgs_in_complete_turns, \
    f"JSONL should have {total_msgs_in_complete_turns} lines, got {len(jsonl_lines)}"

for i, data in enumerate(jsonl_lines):
    assert 'type' not in data or data.get('type') not in ('compress_boundary', 'turn_boundary'), \
        f"Line {i} should not contain boundary markers: {data}"
print("  JSONL verified: no boundary markers, only complete turn messages")
print()

print("=" * 60)
print("Phase 10: Metadata format verification")
print("=" * 60)

md_path = os.path.join(str(session_dir), session.id + '.md')
with open(md_path, 'r') as f:
    md_content = f.read()

print(md_content)

assert f'id: {session.id}' in md_content
assert 'window_start: 0' in md_content
assert f'turn_count: {session.turn_count}' in md_content
assert f'total_input_cost_tokens: {session.total_input_cost_tokens}' in md_content
assert f'total_output_cost_tokens: {session.total_output_cost_tokens}' in md_content

for i in range(session.turn_count):
    assert f'## Turn {i}' in md_content, f"Turn {i} should be in metadata"
    turn = session.get_turn(i)
    assert f'is_summarized: {str(turn.is_summarized).lower()}' in md_content
    assert f'input_tokens: {turn.input_tokens}' in md_content
    assert f'output_tokens: {turn.output_tokens}' in md_content
print("  Metadata format verified")
print()

print("=" * 60)
print("Phase 11: fork with custom session_root")
print("=" * 60)

custom_root = tmp + '_fork_custom'
forked_custom = session.fork(session_root=custom_root)
print(f"  Fork id: {forked_custom.id}")
print(f"  Fork dir: {forked_custom.dir}")
assert os.path.normpath(str(forked_custom.dir)).startswith(os.path.normpath(custom_root)), \
    f"Expected {forked_custom.dir} to start with {custom_root}"
assert forked_custom.turn_count == session.turn_count
assert forked_custom.total_input_cost_tokens == session.total_input_cost_tokens
print("  Custom root fork verified")
print()

print("=" * 60)
print("ALL ASSERTIONS PASSED!")
print("=" * 60)
