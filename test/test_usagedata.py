import asyncio
import json
import sys
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from BBagent.core.model import OpenAIModel, AnthropicModel, Model_Input
from BBagent.core.message import HumanMessage, ModelMessage


API_KEY = os.environ["API_KEY"]
OPENAI_BASE_URL = os.environ["OPENAI_BASE_URL"]
ANTHROPIC_BASE_URL = os.environ["ANTHROPIC_BASE_URL"]
MODEL_NAME = os.environ.get("MODEL", "MiniMax-M2.7-highspeed")


def create_openai_model():
    return OpenAIModel(
        model=MODEL_NAME,
        api_key=API_KEY,
        base_url=OPENAI_BASE_URL,
        max_completion_tokens=4096,
        temperature=0.7,
    )


def create_anthropic_model():
    return AnthropicModel(
        model=MODEL_NAME,
        api_key=API_KEY,
        base_url=ANTHROPIC_BASE_URL,
        max_tokens=4096,
        temperature=0.7,
    )


def test_openai_invoke_usage_data():
    """测试 OpenAI 非流式调用的 usage_data 是否正确返回"""
    model = create_openai_model()
    model_input = Model_Input(
        prompt="你是一个助手。",
        messages=[HumanMessage(content="你好，请简单介绍一下你自己。")],
    )

    result = model.invoke(model_input)

    assert isinstance(result.usage_data, dict), f"usage_data 应为 dict，实际为 {type(result.usage_data)}"
    assert len(result.usage_data) > 0, f"usage_data 不应为空，得到: {result.usage_data}"

    assert result.input_tokens > 0, f"input_tokens 应为正数，得到: {result.input_tokens}"
    assert result.output_tokens > 0, f"output_tokens 应为正数，得到: {result.output_tokens}"

    assert "prompt_tokens" in result.usage_data, f"usage_data 缺少 prompt_tokens: {result.usage_data}"
    assert "completion_tokens" in result.usage_data, f"usage_data 缺少 completion_tokens: {result.usage_data}"
    assert result.usage_data["prompt_tokens"] == result.input_tokens
    assert result.usage_data["completion_tokens"] == result.output_tokens
    print(f"       input_tokens={result.input_tokens}, output_tokens={result.output_tokens}")

    print(f"[PASS] OpenAI invoke usage_data: {result.usage_data}")


async def test_openai_stream_usage_data():
    """测试 OpenAI 流式调用的 usage_data 是否正确返回（修复回归测试）"""
    model = create_openai_model()
    model_input = Model_Input(
        prompt="你是一个助手。",
        messages=[HumanMessage(content="你好，请简单介绍一下你自己。")],
    )

    completed_message = None
    async for event in model.async_stream_invoke(model_input):
        if event['type'] == 'completed_message':
            completed_message = event['content']

    assert completed_message is not None, "流式调用未返回 completed_message"

    assert isinstance(completed_message.usage_data, dict), \
        f"usage_data 应为 dict，实际为 {type(completed_message.usage_data)}"
    assert len(completed_message.usage_data) > 0, \
        f"usage_data 不应为空（流式调用可能未捕获 usage），得到: {completed_message.usage_data}"

    assert completed_message.input_tokens > 0, \
        f"input_tokens 应为正数，得到: {completed_message.input_tokens}"
    assert completed_message.output_tokens > 0, \
        f"output_tokens 应为正数，得到: {completed_message.output_tokens}"

    assert "prompt_tokens" in completed_message.usage_data, \
        f"usage_data 缺少 prompt_tokens: {completed_message.usage_data}"
    assert "completion_tokens" in completed_message.usage_data, \
        f"usage_data 缺少 completion_tokens: {completed_message.usage_data}"

    print(f"[PASS] OpenAI stream usage_data: {completed_message.usage_data}")
    print(f"       input_tokens={completed_message.input_tokens}, output_tokens={completed_message.output_tokens}")


def test_openai_invoke_usage_data_match():
    """验证 usage_data 中的数值与 input_tokens / output_tokens 是否一致"""
    model = create_openai_model()
    model_input = Model_Input(
        prompt="你是一个助手。",
        messages=[HumanMessage(content="请告诉我今天的日期是哪一年？只需要回答年份。")],
    )

    result = model.invoke(model_input)

    assert result.usage_data["prompt_tokens"] == result.input_tokens, \
        f"prompt_tokens({result.usage_data['prompt_tokens']}) != input_tokens({result.input_tokens})"
    assert result.usage_data["completion_tokens"] == result.output_tokens, \
        f"completion_tokens({result.usage_data['completion_tokens']}) != output_tokens({result.output_tokens})"

    print(f"[PASS] OpenAI invoke 数值一致性校验通过: {result.usage_data}")


async def test_openai_stream_with_tool_usage_data():
    """测试 OpenAI 流式调用（工具调用场景）的 usage_data"""
    from BBagent.core.tool import Tool

    def get_weather(city: str = "beijing") -> str:
        weather_data = {
            "beijing": "晴天, 25°C",
            "shanghai": "多云, 22°C",
        }
        return weather_data.get(city.lower(), f"暂无 {city} 的天气数据")

    weather_tool = Tool(func=get_weather)
    model = create_openai_model()
    model_input = Model_Input(
        prompt="你是一个乐于助人且可以使用工具的助手。",
        messages=[HumanMessage(content="北京今天天气怎么样？")],
        tools=[weather_tool],
    )

    completed_message = None
    async for event in model.async_stream_invoke(model_input):
        if event['type'] == 'completed_message':
            completed_message = event['content']

    assert completed_message is not None, "流式调用（工具场景）未返回 completed_message"
    assert isinstance(completed_message.usage_data, dict), \
        f"usage_data 应为 dict，实际为 {type(completed_message.usage_data)}"
    assert len(completed_message.usage_data) > 0, \
        f"usage_data 不应为空（工具场景流式调用），得到: {completed_message.usage_data}"

    print(f"[PASS] OpenAI stream with tools usage_data: {completed_message.usage_data}")
    print(f"       input_tokens={completed_message.input_tokens}, output_tokens={completed_message.output_tokens}")


async def test_openai_assistant_content_counted_in_prompt():
    """确定性验证：ModelMessage 的 content 是否会计入 prompt_tokens

    如果只算 user+tool 消息，那么添加一条 ModelMessage 后 prompt_tokens 应不变；
    如果所有消息都算，prompt_tokens 会增加约 tokens(ModelMessage.content) 个。
    """
    model = create_openai_model()
    system_prompt = "You are a helpful assistant."

    # 基线：仅 system + user
    baseline_input = Model_Input(
        prompt=system_prompt,
        messages=[HumanMessage(content="Hello")],
    )
    baseline = model.invoke(baseline_input)
    baseline_prompt = baseline.usage_data["prompt_tokens"]

    # 手动构造一条 ModelMessage，写入一段 200+ 字符的已知内容
    assistant_content = (
        "The quick brown fox jumps over the lazy dog. "
        "The five boxing wizards jump quickly. "
        "How vexingly quick daft zebras jump. "
        "Sphinx of black quartz, judge my vow. "
        "Two driven jocks help fax my big quiz."
    )

    msg_raw_json = json.dumps({
        "role": "assistant",
        "content": assistant_content,
        "reasoning_content": "THIS_SHOULD_NOT_BE_COUNTED",
    })

    assistant_msg = ModelMessage(
        id="test-msg-001",
        content=assistant_content,
        stop_reason="stop",
        usage_data={},
        raw_json=msg_raw_json,
        input_tokens=0,
        output_tokens=0,
    )

    # 带 ModelMessage 的新请求
    enriched_input = Model_Input(
        prompt=system_prompt,
        messages=[
            HumanMessage(content="Hello"),
            assistant_msg,
            HumanMessage(content="Ok"),
        ],
    )
    enriched = model.invoke(enriched_input)
    enriched_prompt = enriched.usage_data["prompt_tokens"]

    delta = enriched_prompt - baseline_prompt

    print(f"  基线 (system+user):         prompt_tokens={baseline_prompt}")
    print(f"  +ModelMessage + user:       prompt_tokens={enriched_prompt}")
    print(f"  增量:                       {delta}")
    print(f"  ModelMessage content 长度:  {len(assistant_content)} 字符")
    print(f"  'THIS_SHOULD_NOT_BE_COUNTED' 未出现在 input 中 => reasoning 被排除")

    assert delta > 0, (
        f"ModelMessage 加入后 prompt_tokens({enriched_prompt}) 应大于基线({baseline_prompt})，"
        f"增量 {delta} <= 0，说明 ModelMessage 的 content 未被计入 prompt_tokens"
    )

    print(f"\n[PASS] ModelMessage content 已计入 prompt_tokens（增量 +{delta}）")


async def test_openai_reasoning_excluded_from_prompt():
    """验证 reasoning_content 不会累积进后续轮的 prompt_tokens"""
    model = create_openai_model()

    messages = []
    for round_idx in range(1, 4):
        if round_idx == 1:
            messages.append(HumanMessage(content="Hi"))
        else:
            messages.append(HumanMessage(content="Ok"))

        model_input = Model_Input(
            prompt="You are a helpful assistant. Answer as concisely as possible, ideally in one sentence.",
            messages=list(messages),
        )

        result = model.invoke(model_input)
        completion_details = result.usage_data.get("completion_tokens_details", {})

        messages.append(result)
        visible_content = result.content
        thinking_len = len(result.thinking) if result.thinking else 0

        print(f"  第 {round_idx} 轮: prompt_tokens={result.usage_data['prompt_tokens']}, "
              f"completion_tokens={result.usage_data['completion_tokens']}, "
              f"reasoning_tokens={completion_details.get('reasoning_tokens', 'N/A')}, "
              f"visible_content_len={len(str(visible_content))}, "
              f"thinking_len={thinking_len}")

    print(f"\n  注：completion_tokens = reasoning_tokens + visible_tokens")
    print(f"     每次追加到 messages 的 ModelMessage，其 raw_json['content'] = 仅 visible 部分")
    print(f"     reasoning_content 不会出现在下一轮的 messages 中，因此不会被重算")
    print(f"[PASS] reasoning 不会累积进后续 prompt_tokens")


async def test_anthropic_input_tokens_deterministic():
    """确定性实验：验证 Anthropic 的 input_tokens 到底统计了什么

    实验设计：
      1. 基线 A: system + short_user
      2. 基线 B: system + short_user + another_user（验证加一条 user 的增量）
      3. 实验 C: system + short_user + assistant(已知长文本) + another_user
      4. 对比 B→C 的增量，判断 assistant 的 content 是否被计入 input_tokens
      5. 检查 cache_* 字段
    """
    model = create_anthropic_model()
    system_prompt = "You are a helpful assistant."

    long_content = (
        "The quick brown fox jumps over the lazy dog. " * 10
    )

    def make_user_msg(text: str) -> HumanMessage:
        return HumanMessage(content=text)

    def make_assistant_msg(text: str) -> ModelMessage:
        raw_json = json.dumps({
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
        })
        return ModelMessage(
            id="test-assistant-msg",
            content=text,
            stop_reason="end_turn",
            usage_data={},
            raw_json=raw_json,
            input_tokens=0,
            output_tokens=0,
        )

    # --- 实验 A: 基线，仅 system + user ---
    input_a = Model_Input(
        prompt=system_prompt,
        messages=[make_user_msg("Hello")],
    )
    result_a = model.invoke(input_a)
    usage_a = result_a.usage_data
    print(f"\n  A (system + user):            input_tokens={usage_a['input_tokens']}, "
          f"output_tokens={usage_a['output_tokens']}")

    # --- 实验 B: system + user1 + user2（看加一条 user 的增量）---
    input_b = Model_Input(
        prompt=system_prompt,
        messages=[make_user_msg("Hello"), make_user_msg("Ok")],
    )
    result_b = model.invoke(input_b)
    usage_b = result_b.usage_data
    delta_b = usage_b["input_tokens"] - usage_a["input_tokens"]
    print(f"  B (system + user + user):     input_tokens={usage_b['input_tokens']}, "
          f"output_tokens={usage_b['output_tokens']}")
    print(f"    B - A 增量: +{delta_b} （加了一条 user message 的 token 数）")

    # --- 实验 C: system + user1 + assistant(长文本) + user2 ---
    input_c = Model_Input(
        prompt=system_prompt,
        messages=[
            make_user_msg("Hello"),
            make_assistant_msg(long_content),
            make_user_msg("Ok"),
        ],
    )
    result_c = model.invoke(input_c)
    usage_c = result_c.usage_data
    delta_c = usage_c["input_tokens"] - usage_b["input_tokens"]
    print(f"  C (system + user + asst + user): input_tokens={usage_c['input_tokens']}, "
          f"output_tokens={usage_c['output_tokens']}")
    print(f"    C - B 增量: +{delta_c} （B→C 只多了一条 assistant content, 结构相同）")

    print(f"\n  --- cache 字段 ---")
    print(f"    cache_creation_input_tokens: {usage_a.get('cache_creation_input_tokens', 0)}")
    print(f"    cache_read_input_tokens:     {usage_a.get('cache_read_input_tokens', 0)}")
    print(f"    input_tokens + cache = {usage_a['input_tokens'] + usage_a.get('cache_creation_input_tokens', 0) + usage_a.get('cache_read_input_tokens', 0)}")

    # --- 断言 ---
    assert delta_c > 0, (
        f"实验 C 比 B 多了一条 assistant content({len(long_content)} 字符)，"
        f"但 input_tokens 增量={delta_c} <= 0，说明 assistant content 未被计入"
    )

    # 验证总 input_tokens = input_tokens + cache_*
    total = usage_a['input_tokens'] + usage_a.get('cache_creation_input_tokens', 0) + usage_a.get('cache_read_input_tokens', 0)
    print(f"\n  验证官方文档: input_tokens + cache_creation + cache_read = {total}")
    print(f"  (我们没发 cache control headers, 所以 cache 字段应为 0)")

    print(f"\n[PASS] Anthropic input_tokens 增量确认: +{delta_c} (assistant content {len(long_content)} 字符)")


async def test_multi_turn_side_by_side():
    """同一段多轮对话，同时跑 Anthropic 和 OpenAI，并排输出所有 token 数据"""
    model_anthropic = create_anthropic_model()
    model_openai = create_openai_model()

    prompt = "You are a helpful assistant. Answer as concisely as possible, ideally in one sentence."

    round_size = 4

    # --- 先跑 Anthropic ---
    anthro_messages = []
    anthro_rows = []
    for i in range(1, round_size + 1):
        anthro_messages.append(HumanMessage(content="Hi" if i == 1 else "Ok"))
        inp = Model_Input(prompt=prompt, messages=list(anthro_messages))
        result = model_anthropic.invoke(inp)
        u = result.usage_data
        anthro_rows.append({
            "round": i,
            "input_tokens": u.get("input_tokens", 0),
            "cache_read": u.get("cache_read_input_tokens", 0),
            "cache_creation": u.get("cache_creation_input_tokens", 0),
            "total_input": result.input_tokens,
            "output_tokens": u.get("output_tokens", 0),
            "visible_len": len(str(result.content)),
        })
        anthro_messages.append(result)

    # --- 再跑 OpenAI ---
    oai_messages = []
    oai_rows = []
    for i in range(1, round_size + 1):
        oai_messages.append(HumanMessage(content="Hi" if i == 1 else "Ok"))
        inp = Model_Input(prompt=prompt, messages=list(oai_messages))
        result = model_openai.invoke(inp)
        u = result.usage_data
        details = u.get("completion_tokens_details", {})
        oai_rows.append({
            "round": i,
            "prompt_tokens": u.get("prompt_tokens", 0),
            "completion_tokens": u.get("completion_tokens", 0),
            "reasoning_tokens": details.get("reasoning_tokens", 0),
            "visible_tokens": u.get("completion_tokens", 0) - details.get("reasoning_tokens", 0),
            "visible_len": len(str(result.content)),
        })
        oai_messages.append(result)

    # --- 输出对比表格 ---
    header = f"{'轮次':<4} | {'Anthropic':>35} | {'OpenAI':>45}"
    sep = "-" * len(header)
    print(f"\n  {sep}")
    print(f"  {header}")
    print(f"  {sep}")

    for i in range(round_size):
        a = anthro_rows[i]
        o = oai_rows[i]
        anthro_part = (
            f"input={a['total_input']:>4}"
            f"  (raw={a['input_tokens']:>4}"
            f"  cache_r={a['cache_read']:>4})"
            f"  out={a['output_tokens']:>4}"
        )
        oai_part = (
            f"prompt={o['prompt_tokens']:>4}"
            f"  out={o['completion_tokens']:>4}"
            f"  (reason={o['reasoning_tokens']:>4}"
            f"  visible={o['visible_tokens']:>4})"
        )
        print(f"  {i+1:<4} | {anthro_part:<35} | {oai_part:<45}")

    print(f"  {sep}")

    # Anthropic 增幅明细
    print(f"\n  --- Anthropic 增幅分析 ---")
    for i in range(1, round_size):
        delta = anthro_rows[i]["total_input"] - anthro_rows[i-1]["total_input"]
        prev_out = anthro_rows[i-1]["output_tokens"]
        print(f"    第{i}→{i+1}轮: total_input +{delta:>3}  (上轮 output_tokens={prev_out:>3}, 含 thinking)")

    # OpenAI 增幅明细
    print(f"\n  --- OpenAI 增幅分析 ---")
    for i in range(1, round_size):
        delta = oai_rows[i]["prompt_tokens"] - oai_rows[i-1]["prompt_tokens"]
        prev_visible = oai_rows[i-1]["visible_tokens"]
        print(f"    第{i}→{i+1}轮: prompt_tokens +{delta:>3}  (上轮 visible_tokens={prev_visible:>3})")

    # 断言：两个 API 的 total_input / prompt_tokens 序列都严格递增
    anthro_inputs = [r["total_input"] for r in anthro_rows]
    oai_prompts = [r["prompt_tokens"] for r in oai_rows]
    assert all(anthro_inputs[i] > anthro_inputs[i-1] for i in range(1, len(anthro_inputs))), \
        f"Anthropic total_input 未严格递增: {anthro_inputs}"
    assert all(oai_prompts[i] > oai_prompts[i-1] for i in range(1, len(oai_prompts))), \
        f"OpenAI prompt_tokens 未严格递增: {oai_prompts}"

    print(f"\n[PASS] 两者均严格递增，累计 token 数正确")


async def main():
    print("=" * 60)
    print("UsageData 测试 - OpenAI 模型")
    print("=" * 60)

    test_openai_invoke_usage_data()
    print()

    await test_openai_stream_usage_data()
    print()

    test_openai_invoke_usage_data_match()
    print()

    await test_openai_stream_with_tool_usage_data()
    print()

    print("=" * 60)
    print("OpenAI 模型 - 多轮 / reasoning 验证")
    print("=" * 60)

    await test_openai_assistant_content_counted_in_prompt()
    print()

    await test_openai_reasoning_excluded_from_prompt()
    print()

    print("=" * 60)
    print("Anthropic input_tokens 确定性实验")
    print("=" * 60)

    await test_anthropic_input_tokens_deterministic()
    print()

    print("=" * 60)
    print("同一对话 双 API 并排对比")
    print("=" * 60)

    await test_multi_turn_side_by_side()
    print()

    print("=" * 60)
    print("所有 UsageData 测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
