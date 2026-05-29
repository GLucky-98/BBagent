import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from BBagent.core.model import AnthropicModel, OpenAIModel, Model_Input
from BBagent.core.message import HumanMessage, ModelMessage, ToolMessage
from BBagent.core.tool import Tool

# ========================================================================
# 测试工具定义
# ========================================================================
def get_weather(city: str = 'beijing') -> str:
    """获取城市当前天气,城市名称使用拼音小写，不要直接使用中文"""
    weather_data = {
        "beijing": "晴天, 25°C",
        "shanghai": "多云, 22°C",
        "guangzhou": "雨天, 20°C",
        "shenzhen": "晴天, 28°C",
        "hangzhou": "大风, 23°C"
    }
    return weather_data.get(city.lower(), f"暂无 {city} 的天气数据")

def calculate(a: int, b: int, operation: str = "add") -> float:
    """执行基本数学运算,计算符号为add、subtract、multiply、divide"""
    operations = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": a / b if b != 0 else "不能除以零"
    }
    return operations.get(operation.lower(), f"未知运算: {operation}")

# 创建工具实例
weather_tool = Tool(func=get_weather)
calc_tool = Tool(func=calculate)

# ========================================================================
# 测试函数（保留四个核心测试）
# ========================================================================

async def test_anthropic_stream_multi_turn():
    """测试 Anthropic 流式调用 - 多轮对话（5轮以上）"""
    print("\n" + "="*60)
    print("测试 Anthropic 模型 - 流式调用多轮对话")
    print("="*60)
    
    anthropic = AnthropicModel(
        model="MiniMax-M2.7",
        base_url="https://api.minimaxi.com/anthropic",
        api_key="sk-cp-bUj_B29rHYv6jkgSYaH0-lcVdc60QePILOZPOhFFeCzr-83SjvnKl7X9aUCalb131hh11fZMIjcwCeIebxNYQCvnAysNOdCoESKO6rbrdht0k5xcMstSg_M",
        max_tokens=100000,
        temperature=1
    )
    
    messages = [
        HumanMessage(content="你好，请帮我查一下北京今天的天气")
    ]
    
    model_input = Model_Input(
        prompt="你是一个乐于助人且可以使用工具的助手。",
        messages=messages,
        tools=[weather_tool]
    )
    
    try:
        for round_num in range(1, 7):
            print(f"\n--- 第 {round_num} 轮 ---")
            full_content = ""
            tool_calls = []
            completed_message = None
            
            async for event in anthropic.async_stream_invoke(model_input):
                event_type = event.get('type')
                if event_type == 'text':
                    print(event['content'], end='', flush=True)
                    full_content += event['content']
                elif event_type == 'thinking':
                    print(f"\n[思考: {event['content']}]", end='', flush=True)
                elif event_type == 'completed_tool_use':
                    tool_calls.append(event['content'])
                    print(f"\n[工具调用完成: {event['content'].name}]", flush=True)
                elif event_type == 'completed_message':
                    completed_message = event['content']
            
            print()
            
            if tool_calls:
                for tool_call in tool_calls:
                    tool_func = next((t for t in [weather_tool] if t.name == tool_call.name), None)
                    if tool_func:
                        tool_result = tool_func.invoke(tool_call.input)
                        print(f"工具调用结果: {tool_result}")
                        messages.append(completed_message)
                        messages.append(ToolMessage(
                            id=tool_call.id,
                            name=tool_call.name,
                            content=str(tool_result)
                        ))
                        cities = ["上海", "广州", "深圳", "杭州", "北京"]
                        if round_num < len(cities):
                            messages.append(HumanMessage(content=f"好的，再帮我查一下{cities[round_num-1]}的天气"))
                    break
                
                if round_num < 6:
                    model_input = Model_Input(
                        prompt="你是一个乐于助人且可以使用工具的助手。",
                        messages=messages,
                        tools=[weather_tool]
                    )
            else:
                if completed_message:
                    messages.append(completed_message)
                print(f"\n模型直接回答，无需工具调用")
                break
        
        print(f"\n共完成 {len(messages)} 条消息交换")
        print(f"消息类型序列: {[type(m).__name__ for m in messages]}")
    except Exception as e:
        print(f"错误: {e}")


async def test_openai_stream_multi_turn():
    """测试 OpenAI 流式调用 - 多轮对话（5轮以上）"""
    print("\n" + "="*60)
    print("测试 OpenAI 模型 - 流式调用多轮对话")
    print("="*60)
    
    # openai = OpenAIModel(
    #     model="mimo-v2.5-pro",
    #     base_url="https://token-plan-cn.xiaomimimo.com/v1",
    #     api_key="tp-c72lhg031y2x08me0upyc9pn9ol7qije2v1swndodi9z3ohq",
    #     max_completion_tokens=100000,
    #     temperature=1
    # )
    
    openai = OpenAIModel(
        model="MiniMax-M2.7-highspeed",
        base_url="https://api.minimaxi.com/v1",
        api_key="sk-cp-bUj_B29rHYv6jkgSYaH0-lcVdc60QePILOZPOhFFeCzr-83SjvnKl7X9aUCalb131hh11fZMIjcwCeIebxNYQCvnAysNOdCoESKO6rbrdht0k5xcMstSg_M",
        max_completion_tokens=100000,
        temperature=1
    )

    messages = [
        HumanMessage(content="你好，请计算 50 乘以 12")
    ]
    
    model_input = Model_Input(
        prompt="你是一个乐于助人且可以使用工具的助手。",
        messages=messages,
        tools=[calc_tool]
    )
    
    try:
        for round_num in range(1, 7):
            print(f"\n--- 第 {round_num} 轮 ---")
            full_content = ""
            tool_calls = []
            completed_message = None
            
            async for event in openai.async_stream_invoke(model_input):
                event_type = event.get('type')
                if event_type == 'text':
                    print(event['content'], end='', flush=True)
                    full_content += event['content']
                elif event_type == 'thinking':
                    print(f"\n[思考: {event['content']}]", end='', flush=True)
                elif event_type == 'completed_tool_use':
                    tool_calls.append(event['content'])
                    print(f"\n[工具调用完成: {event['content'].name}]", flush=True)
                elif event_type == 'completed_message':
                    completed_message = event['content']
            
            print()
            
            if tool_calls:
                for tool_call in tool_calls:
                    tool_func = next((t for t in [calc_tool] if t.name == tool_call.name), None)
                    if tool_func:
                        tool_result = tool_func.invoke(tool_call.input)
                        print(f"工具调用 ({tool_call.name}): {tool_result}")
                        messages.append(completed_message)
                        messages.append(ToolMessage(
                            id=tool_call.id,
                            name=tool_call.name,
                            content=str(tool_result)
                        ))
                        messages.append(HumanMessage(content=f"好的，再计算 {tool_result} 加 20"))
                    break
                
                if round_num < 6:
                    model_input = Model_Input(
                        prompt="你是一个乐于助人且可以使用工具的助手。",
                        messages=messages,
                        tools=[calc_tool]
                    )
            else:
                if completed_message:
                    messages.append(completed_message)
                print(f"\n模型直接回答，无需工具调用")
                break
        
        print(f"\n共完成 {len(messages)} 条消息交换")
        print(f"消息列表: {[(type(m).__name__, m.role if hasattr(m, 'role') else '') for m in messages]}")
    except Exception as e:
        print(f"错误: {e}")


async def test_openai_stream_multi_tool_types():
    """测试 OpenAI 流式调用 - 使用多种工具类型（计算器+天气）"""
    print("\n" + "="*60)
    print("测试 OpenAI 模型 - 流式调用多种工具")
    print("="*60)
    
    openai = OpenAIModel(
        model="MiniMax-M2.7-highspeed",
        base_url="https://api.minimaxi.com/v1",
        api_key="sk-cp-bUj_B29rHYv6jkgSYaH0-lcVdc60QePILOZPOhFFeCzr-83SjvnKl7X9aUCalb131hh11fZMIjcwCeIebxNYQCvnAysNOdCoESKO6rbrdht0k5xcMstSg_M",
        max_completion_tokens=100000,
        temperature=1
    )
    
    messages = [
        HumanMessage(content="请先计算 10 + 20，然后告诉我结果")
    ]
    
    model_input = Model_Input(
        prompt="你是一个乐于助人且可以使用工具的助手。",
        messages=messages,
        tools=[calc_tool, weather_tool]
    )
    
    try:
        print("\n--- 第 1 轮：计算 ---")
        tool_calls = []
        completed_message = None
        
        async for event in openai.async_stream_invoke(model_input):
            event_type = event.get('type')
            if event_type == 'text':
                print(event['content'], end='', flush=True)
            elif event_type == 'thinking':
                print(f"\n[思考: {event['content']}]", end='', flush=True)
            elif event_type == 'completed_tool_use':
                tool_calls.append(event['content'])
                print(f"\n[工具调用完成: {event['content'].name}]", flush=True)
            elif event_type == 'completed_message':
                completed_message = event['content']
        
        print()
        
        if tool_calls:
            tool_call = tool_calls[0]
            tool_func = next((t for t in [calc_tool, weather_tool] if t.name == tool_call.name), None)
            if tool_func:
                result = tool_func.invoke(tool_call.input)
                print(f"计算结果: {result}")
                
                messages.append(completed_message)
                messages.append(ToolMessage(
                    id=tool_call.id,
                    name=tool_call.name,
                    content=str(result)
                ))
                
                messages.append(HumanMessage(content=f"计算结果是{result}，现在请查一下北京的天气"))
                model_input = Model_Input(
                    prompt="你是一个乐于助人且可以使用工具的助手。",
                    messages=messages,
                    tools=[calc_tool, weather_tool]
                )
                
                print("\n--- 第 2 轮：天气查询 ---")
                tool_calls = []
                completed_message = None
                
                async for event in openai.async_stream_invoke(model_input):
                    event_type = event.get('type')
                    if event_type == 'text':
                        print(event['content'], end='', flush=True)
                    elif event_type == 'thinking':
                        print(f"\n[思考: {event['content']}]", end='', flush=True)
                    elif event_type == 'completed_tool_use':
                        tool_calls.append(event['content'])
                        print(f"\n[工具调用完成: {event['content'].name}]", flush=True)
                    elif event_type == 'completed_message':
                        completed_message = event['content']
                
                print()
                
                if tool_calls:
                    tool_call = tool_calls[0]
                    tool_func = next((t for t in [calc_tool, weather_tool] if t.name == tool_call.name), None)
                    if tool_func:
                        result = tool_func.invoke(tool_call.input)
                        print(f"天气查询结果: {result}")
        
        print(f"\n测试完成！消息总数: {len(messages)}")
    except Exception as e:
        print(f"错误: {e}")


async def test_anthropic_stream_multi_tool_types():
    """测试 Anthropic 流式调用 - 使用多种工具类型"""
    print("\n" + "="*60)
    print("测试 Anthropic 模型 - 流式调用多种工具")
    print("="*60)
    
    anthropic = AnthropicModel(
        model="MiniMax-M2.7-highspeed",
        base_url="https://api.minimaxi.com/anthropic",
        api_key="sk-cp-bUj_B29rHYv6jkgSYaH0-lcVdc60QePILOZPOhFFeCzr-83SjvnKl7X9aUCalb131hh11fZMIjcwCeIebxNYQCvnAysNOdCoESKO6rbrdht0k5xcMstSg_M",
        max_tokens=100000,
        temperature=1
    )
    
    messages = [
        HumanMessage(content="先帮我查一下上海的天气，然后计算 50 除以 10")
    ]
    
    model_input = Model_Input(
        prompt="你是一个乐于助人且可以使用工具的助手。",
        messages=messages,
        tools=[weather_tool, calc_tool]
    )
    
    try:
        print("\n--- 第 1 轮：天气查询 ---")
        tool_calls = []
        completed_message = None
        
        async for event in anthropic.async_stream_invoke(model_input):
            event_type = event.get('type')
            if event_type == 'text':
                print(event['content'], end='', flush=True)
            elif event_type == 'thinking':
                print(f"\n[思考: {event['content']}]", end='', flush=True)
            elif event_type == 'completed_tool_use':
                tool_calls.append(event['content'])
                print(f"\n[工具调用完成: {event['content'].name}]", flush=True)
            elif event_type == 'completed_message':
                completed_message = event['content']
        
        print()
        
        if tool_calls:
            messages.append(completed_message)
            for tc in tool_calls:
                tool_func = next((t for t in [weather_tool, calc_tool] if t.name == tc.name), None)
                if tool_func:
                    result = tool_func.invoke(tc.input)
                    print(f"工具执行结果 ({tc.name}): {result}")
                    messages.append(ToolMessage(
                        id=tc.id,
                        name=tc.name,
                        content=str(result)
                    ))

            messages.append(HumanMessage(content="好的，现在计算 50 除以 10"))
            model_input = Model_Input(
                prompt="你是一个乐于助人且可以使用工具的助手。",
                messages=messages,
                tools=[weather_tool, calc_tool]
            )

            print("\n--- 第 2 轮：计算 ---")
            tool_calls = []
            completed_message = None

            async for event in anthropic.async_stream_invoke(model_input):
                event_type = event.get('type')
                if event_type == 'text':
                    print(event['content'], end='', flush=True)
                elif event_type == 'thinking':
                    print(f"\n[思考: {event['content']}]", end='', flush=True)
                elif event_type == 'completed_tool_use':
                    tool_calls.append(event['content'])
                    print(f"\n[工具调用完成: {event['content'].name}]", flush=True)
                elif event_type == 'completed_message':
                    completed_message = event['content']

            print()

            if tool_calls:
                messages.append(completed_message)
                for tc in tool_calls:
                    tool_func = next((t for t in [weather_tool, calc_tool] if t.name == tc.name), None)
                    if tool_func:
                        result = tool_func.invoke(tc.input)
                        print(f"计算结果 ({tc.name}): {result}")
                        messages.append(ToolMessage(
                            id=tc.id,
                            name=tc.name,
                            content=str(result)
                        ))
        
        print(f"\n测试完成！消息总数: {len(messages)}")
    except Exception as e:
        print(f"错误: {e}")

# ========================================================================
# 主测试运行器
# ========================================================================

async def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*60)
    print("开始模型和工具调用测试")
    print("="*60)
    
    await test_anthropic_stream_multi_turn()
    await test_openai_stream_multi_turn()
    await test_openai_stream_multi_tool_types()
    await test_anthropic_stream_multi_tool_types()
    
    print("\n" + "="*60)
    print("所有测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
