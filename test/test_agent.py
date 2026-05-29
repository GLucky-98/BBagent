import asyncio
import json
import os
import shutil
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from BBagent.core.agent import Agent, AgentConfig, AgentState
from BBagent.core.model import AnthropicModel, OpenAIModel, Model_Input
from BBagent.core.message import (
    HumanMessage, ModelMessage, ToolMessage,
    TextBlock, ToolUseBlock, Session,
)
from BBagent.core.tool import Tool
from BBagent.core.skill import Skill
from BBagent.core.hook import AgentHook, HookType, HookContext
from BBagent.built_in_tool import create_all_tools

TEMP_DIR = Path(__file__).parent / "temp"


# ========================================================================
# 模型工厂
# ========================================================================

API_KEY = os.environ["API_KEY"]
ANTHROPIC_BASE_URL = os.environ["ANTHROPIC_BASE_URL"]
OPENAI_BASE_URL = os.environ["OPENAI_BASE_URL"]
MODEL_NAME = os.environ.get("MODEL", "MiniMax-M2.7-highspeed")


def create_anthropic_model():
    return AnthropicModel(
        model=MODEL_NAME,
        api_key=API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        max_tokens=4096,
        temperature=0.7,
    )


def create_openai_model():
    return OpenAIModel(
        model=MODEL_NAME,
        api_key=API_KEY,
        base_url=OPENAI_BASE_URL,
        max_completion_tokens=4096,
        temperature=0.7,
    )


MODEL_FACTORIES = {
    "anthropic": create_anthropic_model,
    "openai": create_openai_model,
}


# ========================================================================
# 内置测试工具
# ========================================================================

def get_weather(city: str = "beijing") -> str:
    """获取城市当前天气,城市名称使用拼音小写，不要直接使用中文"""
    weather_data = {
        "beijing": "晴天, 25°C",
        "shanghai": "多云, 22°C",
        "guangzhou": "雨天, 20°C",
        "shenzhen": "晴天, 28°C",
        "hangzhou": "大风, 23°C",
    }
    return weather_data.get(city.lower(), f"暂无 {city} 的天气数据")


def calculate(a: int, b: int, operation: str = "add") -> float:
    """执行基本数学运算,运算类型为add、subtract、multiply、divide"""
    operations = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else "不能除以零",
    }
    return operations.get(operation.lower(), f"未知运算: {operation}")


# ========================================================================
# 测试 Agent 构建器
# ========================================================================

def make_test_dir(test_name: str, model_name: str, suffix: str = "") -> Path:
    dir_name = f"{test_name}_{model_name}" + (f"_{suffix}" if suffix else "")
    path = TEMP_DIR / dir_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_test_agent(model_name, test_name, tools=None, skills=None, system_prompt=""):
    tmp_dir = make_test_dir(test_name, model_name)
    model = MODEL_FACTORIES[model_name]()
    config = AgentConfig(
        model=model,
        base_dir=str(tmp_dir),
        system_prompt=system_prompt,
        tools=tools or [],
        skills=skills or [],
        hook=AgentHook(),
    )
    agent = Agent(config)
    return agent, tmp_dir


def collect_stream_chunks(agent, msg):
    async def _collect():
        chunks = []
        async for chunk in agent.run(msg):
            chunks.append(chunk)
        return chunks

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, _collect()).result()
    else:
        return asyncio.run(_collect())


def extract_text(chunks):
    parts = []
    for c in chunks:
        if isinstance(c, dict) and c.get("type") == "text":
            parts.append(c["content"])
    return "".join(parts)


def extract_tool_calls(chunks):
    calls = []
    for c in chunks:
        if isinstance(c, dict) and c.get("type") == "completed_tool_use":
            calls.append(c["content"])
    return calls


def extract_tool_results(chunks):
    results = []
    for c in chunks:
        if isinstance(c, dict) and c.get("type") == "tool_results":
            results.extend(c["content"])
    return results


def extract_thinking(chunks):
    parts = []
    for c in chunks:
        if isinstance(c, dict) and c.get("type") == "thinking":
            parts.append(c["content"])
    return "".join(parts)


# ========================================================================
# 1. 基础能力测试
# ========================================================================

def test_simple_text_response(model_name):
    agent, tmp = create_test_agent(model_name, "simple_text")
    chunks = collect_stream_chunks(agent, HumanMessage(content="请回复OK两个字母，不要加任何其他内容"))
    text = extract_text(chunks)
    assert len(text) > 0, "模型没有返回文本"
    assert len(agent.session.messages) == 2
    assert isinstance(agent.session.messages[0], HumanMessage)
    assert isinstance(agent.session.messages[1], ModelMessage)
    print(f"[PASS] test_simple_text_response ({model_name})")


def test_multi_turn_conversation(model_name):
    agent, tmp = create_test_agent(model_name, "multi_turn")
    chunks1 = collect_stream_chunks(agent, HumanMessage(content="我有一个数字5，请记住它"))
    text1 = extract_text(chunks1)
    assert len(text1) > 0

    chunks2 = collect_stream_chunks(agent, HumanMessage(content="刚才的数字乘以3等于多少？只回答数字"))
    text2 = extract_text(chunks2)
    assert len(text2) > 0
    assert "15" in text2

    assert len(agent.session.messages) == 4
    assert agent.session.messages[0].content == "我有一个数字5，请记住它"
    assert agent.session.messages[2].content == "刚才的数字乘以3等于多少？只回答数字"
    print(f"[PASS] test_multi_turn_conversation ({model_name})")


# ========================================================================
# 2. 工具调用测试
# ========================================================================

def test_single_tool_call(model_name):
    weather_tool = Tool(func=get_weather)
    agent, tmp = create_test_agent(model_name, "single_tool", tools=[weather_tool])
    chunks = collect_stream_chunks(
        agent,
        HumanMessage(content="请查询北京的天气，使用get_weather工具"),
    )
    tool_calls = extract_tool_calls(chunks)
    tool_results = extract_tool_results(chunks)

    assert len(tool_calls) >= 1, "模型没有调用工具"
    assert tool_calls[0].name == "get_weather"
    assert len(tool_results) >= 1, "没有工具执行结果"
    assert isinstance(tool_results[0], ToolMessage)

    text = extract_text(chunks)
    assert len(text) > 0, "模型没有生成最终文本回复"

    session_msgs = agent.session.messages
    assert len(session_msgs) >= 4
    print(f"[PASS] test_single_tool_call ({model_name})")


def test_multi_tool_call(model_name):
    weather_tool = Tool(func=get_weather)
    calc_tool = Tool(func=calculate)
    agent, tmp = create_test_agent(model_name, "multi_tool", tools=[weather_tool, calc_tool])
    chunks = collect_stream_chunks(
        agent,
        HumanMessage(content="请帮我查询北京天气，并且计算 100 加 200 等于多少"),
    )
    tool_calls = extract_tool_calls(chunks)
    tool_results = extract_tool_results(chunks)

    assert len(tool_calls) >= 1, "模型没有调用工具"
    tool_names = {tc.name for tc in tool_calls}
    assert len(tool_names) >= 1
    assert len(tool_results) >= 1

    text = extract_text(chunks)
    assert len(text) > 0
    print(f"[PASS] test_multi_tool_call ({model_name})")


def test_tool_round_loop(model_name):
    calc_tool = Tool(func=calculate)
    agent, tmp = create_test_agent(model_name, "tool_round_loop", tools=[calc_tool])
    chunks = collect_stream_chunks(
        agent,
        HumanMessage(content="请计算 (10 + 20) * 3，可以分步调用calculate工具计算。最终回复只写结果数字"),
    )
    tool_calls = extract_tool_calls(chunks)
    tool_results = extract_tool_results(chunks)
    text = extract_text(chunks)

    assert len(tool_calls) >= 1, "模型没有调用工具"
    assert len(tool_results) >= 1, "没有工具执行结果"

    has_mult = any(tc.name == "calculate" for tc in tool_calls)
    assert has_mult, "模型没有使用 calculate 工具"

    assert "90" in text, f"最终结果应为90，实际文本: {text[:200]}"
    print(f"[PASS] test_tool_round_loop ({model_name})")


def test_builtin_tools_integration(model_name):
    loop = asyncio.new_event_loop()
    try:
        tools_dict = loop.run_until_complete(
            create_all_tools(cwd=str(Path(__file__).parent.parent))
        )
        tools = list(tools_dict.values())
        agent, tmp = create_test_agent(model_name, "builtin_tools", tools=tools)

        chunks = collect_stream_chunks(
            agent,
            HumanMessage(content="请使用ls工具列出当前目录的内容，不要使用其他工具"),
        )
        tool_calls = extract_tool_calls(chunks)
        tool_results = extract_tool_results(chunks)

        assert len(tool_calls) >= 1, "模型没有调用工具"
        assert len(tool_results) >= 1

        text = extract_text(chunks)
        assert len(text) > 0

        print(f"[PASS] test_builtin_tools_integration ({model_name})")
    finally:
        loop.close()


# ========================================================================
# 3. Skill 测试
# ========================================================================

def test_skill_in_prompt(model_name):
    skill = Skill(
        name="code-review",
        description="代码审查助手",
        body="# Code Review\n\n帮助审查代码质量",
        path=Path(__file__).parent.parent / "skills" / "code-review",
    )
    agent, tmp = create_test_agent(model_name, "skill_prompt", skills=[skill])
    assert "code-review" in agent.skill_prompt
    assert "代码审查助手" in agent.skill_prompt

    chunks = collect_stream_chunks(agent, HumanMessage(content="你好，请简短介绍一下你自己"))
    text = extract_text(chunks)
    assert len(text) > 0
    print(f"[PASS] test_skill_in_prompt ({model_name})")


# ========================================================================
# 4. Session 管理测试
# ========================================================================

def test_session_persistence(model_name):
    hook = AgentHook()
    agent, tmp = create_test_agent(model_name, "session_persist")
    agent.hook = hook
    hook.set_context(agent)
    chunks = collect_stream_chunks(agent, HumanMessage(content="请回复OK"))
    text = extract_text(chunks)
    assert len(text) > 0

    session_path = agent.session.path
    session_id = agent.session.id
    jsonl_path = session_path / f"{session_id}.jsonl"
    assert jsonl_path.exists(), "Session JSONL 文件未创建"

    with open(jsonl_path, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    assert len(lines) >= 2
    agent.session.save()
    loaded = Session.load(session_id, session_path)
    assert len(loaded.messages) == len(agent.session.messages)
    print(f"[PASS] test_session_persistence ({model_name})")


def test_new_session(model_name):
    hook = AgentHook()
    agent, tmp = create_test_agent(model_name, "new_session")
    agent.hook = hook
    hook.set_context(agent)
    collect_stream_chunks(agent, HumanMessage(content="回复OK"))
    old_session = agent.session
    old_id = old_session.id

    loop = asyncio.new_event_loop()
    loop.run_until_complete(agent.new_session())
    loop.close()

    assert agent.session.id != old_id
    assert len(agent.session.messages) == 0

    jsonl_path = old_session.path / f"{old_id}.jsonl"
    assert jsonl_path.exists(), "旧 session 未保存"
    print(f"[PASS] test_new_session ({model_name})")


# ========================================================================
# 5. Hook 测试
# ========================================================================

def test_hook_events(model_name):
    hook = AgentHook()
    events_log = []

    @hook.hook(HookType.ON_TEXT_CHUNK)
    async def log_text(ctx, chunk):
        events_log.append(("text", chunk))

    @hook.hook(HookType.ON_MESSAGE)
    async def log_message(ctx, msg):
        events_log.append(("message", type(msg).__name__))

    @hook.hook(HookType.BEFORE_STREAM)
    async def log_before(ctx):
        events_log.append(("before_stream", None))

    agent, tmp = create_test_agent(model_name, "hook_events")
    agent.hook = hook
    hook.set_context(agent)
    chunks = collect_stream_chunks(agent, HumanMessage(content="请回复OK"))

    text_events = [e for e in events_log if e[0] == "text"]
    assert len(text_events) > 0, "没有触发 ON_TEXT_CHUNK 事件"

    message_events = [e for e in events_log if e[0] == "message"]
    assert len(message_events) >= 1, "没有触发 ON_MESSAGE 事件"

    before_events = [e for e in events_log if e[0] == "before_stream"]
    assert len(before_events) >= 1, "没有触发 BEFORE_STREAM 事件"

    print(f"[PASS] test_hook_events ({model_name})")


def test_hook_on_tool(model_name):
    hook = AgentHook()
    tool_events = []

    @hook.hook(HookType.ON_TOOL_USE)
    async def log_tool_use(ctx, tool_use):
        tool_events.append(("start", tool_use.name))

    @hook.hook(HookType.ON_TOOL_RESULT)
    async def log_tool_result(ctx, tool_msg):
        tool_events.append(("result", tool_msg.name, tool_msg.content))

    calc_tool = Tool(func=calculate)
    agent, tmp = create_test_agent(model_name, "hook_tool", tools=[calc_tool])
    agent.hook = hook
    hook.set_context(agent)
    chunks = collect_stream_chunks(
        agent,
        HumanMessage(content="请使用calculate工具计算 6 乘以 7"),
    )
    starts = [e for e in tool_events if e[0] == "start"]
    results = [e for e in tool_events if e[0] == "result"]

    assert len(starts) >= 1, "没有触发 ON_TOOL_USE 事件"
    assert starts[0][1] == "calculate"
    assert len(results) >= 1, "没有触发 ON_TOOL_RESULT 事件"
    assert "42" in results[0][2]

    print(f"[PASS] test_hook_on_tool ({model_name})")


# ========================================================================
# 6. Agent 配置与属性测试
# ========================================================================

def test_agent_init_and_config(model_name):
    tmp = make_test_dir("init_config", model_name)
    model = MODEL_FACTORIES[model_name]()
    config = AgentConfig(
        model=[model],
        base_dir=str(tmp),
        system_prompt="Test prompt",
    )
    agent = Agent(config)

    assert agent.state == AgentState.Ready
    assert agent.system_prompt == "Test prompt"
    assert agent.base_dir.exists()
    assert agent.system_prompt_path.exists()
    assert agent.session is not None
    assert agent.session.messages == []
    print(f"[PASS] test_agent_init_and_config ({model_name})")


def test_add_tools(model_name):
    agent, tmp = create_test_agent(model_name, "add_tools")
    t1 = Tool(func=lambda x: x, name="tool_a")
    t2 = Tool(func=lambda y: y, name="tool_b")
    agent.add_tools([t1, t2])

    assert len(agent.tools) == 2
    assert "tool_a" in agent.tools
    assert "tool_b" in agent.tools
    print(f"[PASS] test_add_tools ({model_name})")


def test_change_name(model_name):
    agent, tmp = create_test_agent(model_name, "change_name")
    old_name = agent.name
    agent.change_name("NewAgent")
    assert agent.name == "NewAgent"
    assert agent.name != old_name
    print(f"[PASS] test_change_name ({model_name})")


def test_construct_model_input(model_name):
    weather_tool = Tool(func=get_weather)
    agent, tmp = create_test_agent(
        model_name,
        "construct_input",
        tools=[weather_tool],
        system_prompt="You are helpful.",
    )
    agent.session.add_message(HumanMessage(content="hello"))
    model_input = agent.construct_model_input()

    assert isinstance(model_input, Model_Input)
    assert len(model_input.tools) == 1
    assert model_input.tools[0].name == "get_weather"
    assert "You are helpful." in model_input.prompt
    assert len(model_input.messages) == 1
    print(f"[PASS] test_construct_model_input ({model_name})")


def test_change_base_dir(model_name):
    agent, tmp = create_test_agent(model_name, "change_base")
    new_tmp = make_test_dir("change_base", model_name, suffix="new")
    agent.change_base_dir(new_tmp)
    assert agent.base_dir == Path(new_tmp)
    assert (Path(new_tmp) / "system_prompt.md").exists()
    assert (Path(new_tmp) / "session").exists()
    print(f"[PASS] test_change_base_dir ({model_name})")


# ========================================================================
# 7. 综合测试
# ========================================================================

def test_full_agent_workflow(model_name):
    calc_tool = Tool(func=calculate)
    weather_tool = Tool(func=get_weather)
    skill = Skill(
        name="code-review",
        description="代码审查助手",
        body="# Code Review",
        path=Path(__file__).parent.parent / "skills" / "code-review",
    )

    agent, tmp = create_test_agent(
        model_name,
        "full_workflow",
        tools=[calc_tool, weather_tool],
        skills=[skill],
        system_prompt="你是一个乐于助人的AI助手，可以使用工具回答问题。",
    )
    chunks1 = collect_stream_chunks(
        agent,
        HumanMessage(content="请计算 23 乘以 17 等于多少"),
    )
    text1 = extract_text(chunks1)
    assert len(text1) > 0
    assert "391" in text1

    chunks2 = collect_stream_chunks(
        agent,
        HumanMessage(content="请查一下上海的天气"),
    )
    text2 = extract_text(chunks2)
    assert len(text2) > 0
    tool_calls2 = extract_tool_calls(chunks2)
    assert len(tool_calls2) >= 1

    assert len(agent.session.messages) >= 6
    print(f"[PASS] test_full_agent_workflow ({model_name})")


# ========================================================================
# Main
# ========================================================================

ALL_TESTS = [
    ("基础: 简单文本回复", test_simple_text_response),
    ("基础: 多轮对话", test_multi_turn_conversation),
    ("工具: 单工具调用", test_single_tool_call),
    ("工具: 多工具调用", test_multi_tool_call),
    ("工具: 多轮工具循环", test_tool_round_loop),
    ("工具: 内置工具集成", test_builtin_tools_integration),
    ("Skill: Skill注入Prompt", test_skill_in_prompt),
    ("Session: 持久化", test_session_persistence),
    ("Session: 新建会话", test_new_session),
    ("Hook: 文本与消息事件", test_hook_events),
    ("Hook: 工具事件", test_hook_on_tool),
    ("配置: 初始化与配置", test_agent_init_and_config),
    ("配置: 添加工具", test_add_tools),
    ("配置: 修改名称", test_change_name),
    ("配置: 构建模型输入", test_construct_model_input),
    ("配置: 修改基础路径", test_change_base_dir),
    ("综合: 完整工作流", test_full_agent_workflow),
]


def run_tests(model_name, indices=None):
    print(f"\n{'='*60}")
    print(f"  模型类型: {model_name}")
    print(f"{'='*60}")

    passed = 0
    failed = 0
    errors = []

    targets = indices if indices else range(len(ALL_TESTS))
    for idx in targets:
        name, test_fn = ALL_TESTS[idx]
        try:
            test_fn(model_name)
            passed += 1
        except Exception as e:
            failed += 1
            errors.append((idx + 1, name, e))
            print(f"[FAIL] #{idx+1} {name} ({model_name}): {e}")

    return passed, failed, errors


def parse_test_selection(selection: str):
    indices = []
    for part in selection.split(","):
        part = part.strip()
        if not part:
            continue
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < len(ALL_TESTS):
                indices.append(idx)
            else:
                print(f"警告: 测试编号 {part} 不存在，有效范围: 1-{len(ALL_TESTS)}")
        else:
            found = False
            for i, (name, _) in enumerate(ALL_TESTS):
                if part in name:
                    indices.append(i)
                    found = True
            if not found:
                print(f"警告: 未找到匹配 '{part}' 的测试")
    return sorted(set(indices))


def list_tests():
    print("\n可用测试列表:")
    for i, (name, _) in enumerate(ALL_TESTS, 1):
        print(f"  {i:2d}. {name}")
    print(f"\n测试输出目录: {TEMP_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="Agent 功能完整测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""用法示例:
  python test_agent.py                         运行全部测试
  python test_agent.py --test 3                运行第3项测试
  python test_agent.py --test 3,5,7            运行第3、5、7项测试
  python test_agent.py --test 简单文本          运行名称包含"简单文本"的测试
  python test_agent.py --test Registry          运行所有Registry相关测试
  python test_agent.py --list                   列出所有测试
  python test_agent.py --model anthropic        只用anthropic模型测试

测试输出保存在: {TEMP_DIR}""",
    )
    parser.add_argument(
        "--model",
        choices=["anthropic", "openai", "both"],
        default="both",
        help="选择测试的模型类型 (默认: both)",
    )
    parser.add_argument(
        "--test",
        type=str,
        default=None,
        help="指定要运行的测试: 编号(逗号分隔) 或 名称关键词",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用测试",
    )
    args = parser.parse_args()

    if args.list:
        list_tests()
        return

    if args.model == "both":
        models = ["anthropic", "openai"]
    else:
        models = [args.model]

    indices = None
    if args.test is not None:
        indices = parse_test_selection(args.test)
        if not indices:
            print("没有匹配的测试项")
            return

    print("=" * 60)
    print("  Agent 功能完整测试")
    print(f"  Model: {MODEL_NAME}")
    print(f"  测试范围: {', '.join(models)}")
    if indices:
        selected = [ALL_TESTS[i][0] for i in indices]
        print(f"  选定测试: {', '.join(selected)}")
    print(f"  输出目录: {TEMP_DIR}")
    print("=" * 60)

    total_passed = 0
    total_failed = 0
    all_errors = []

    for model_name in models:
        passed, failed, errors = run_tests(model_name, indices)
        total_passed += passed
        total_failed += failed
        for idx, name, err in errors:
            all_errors.append((idx, name, model_name, err))

    total = total_passed + total_failed
    print(f"\n{'='*60}")
    print(f"  结果: {total_passed}/{total} 通过, {total_failed} 失败")
    print(f"  测试输出: {TEMP_DIR}")
    print(f"{'='*60}")

    if all_errors:
        print("\n失败详情:")
        for idx, name, model, err in all_errors:
            print(f"  - [#{idx}] [{model}] {name}: {err}")

    if indices is None:
        list_tests()


if __name__ == "__main__":
    main()
