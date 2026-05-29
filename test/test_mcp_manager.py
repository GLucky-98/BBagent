import asyncio
import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from BBagent.core.mcp import (
    MCPClient,
    MCPServerConfig,
    parse_config_file,
    load_configs,
)


def test_parse_single_server_format():
    print("=" * 50)
    print("Test 1: parse_config_file - 单服务器格式")
    print("=" * 50)

    single_config = {
        "name": "test-server",
        "command": "python",
        "args": ["-m", "test_server"],
        "env": {"KEY": "value"}
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(single_config, f)
        temp_path = f.name

    try:
        configs = parse_config_file(temp_path)
        assert len(configs) == 1, f"期望 1 个配置，实际: {len(configs)}"
        assert configs[0].name == "test-server"
        assert configs[0].command == "python"
        assert configs[0].env == {"KEY": "value"}
        print("  PASSED\n")
    finally:
        os.unlink(temp_path)


def test_parse_multi_server_format():
    print("=" * 50)
    print("Test 2: parse_config_file - 多服务器格式 (mcpServers)")
    print("=" * 50)

    multi_config = {
        "mcpServers": {
            "server-a": {"command": "npx", "args": ["-y", "server-a"]},
            "server-b": {"command": "python", "args": ["server_b.py"], "env": {"X": "1"}},
            "bad-entry": "not a dict",
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(multi_config, f)
        temp_path = f.name

    try:
        configs = parse_config_file(temp_path)
        assert len(configs) == 2, f"期望 2 个配置（跳过 bad-entry），实际: {len(configs)}"
        names = {c.name for c in configs}
        assert names == {"server-a", "server-b"}, f"名称不匹配: {names}"
        print("  PASSED\n")
    finally:
        os.unlink(temp_path)


def test_load_configs_from_dir():
    print("=" * 50)
    print("Test 3: load_configs - 从目录加载配置")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        config_a = {
            "name": "server-a",
            "command": "echo",
            "args": ["hello"],
        }
        config_b = {
            "mcpServers": {
                "server-b": {"command": "python", "args": ["-c", "print(1)"]},
                "server-c": {"command": "npx", "args": ["-y", "some-pkg"]},
            }
        }
        with open(os.path.join(tmpdir, "a.json"), "w") as f:
            json.dump(config_a, f)
        with open(os.path.join(tmpdir, "b.json"), "w") as f:
            json.dump(config_b, f)
        with open(os.path.join(tmpdir, "readme.txt"), "w") as f:
            f.write("not json")

        result = load_configs(tmpdir)
        assert len(result) == 3, f"期望 3 个配置，实际: {len(result)}"
        assert "server-a" in result
        assert "server-b" in result
        assert "server-c" in result
        assert result["server-a"].command == "echo"
        print(f"  loaded {len(result)} config(s): {list(result.keys())}")
        print("  PASSED\n")


def test_load_configs_empty_dir():
    print("=" * 50)
    print("Test 4: load_configs - 空目录 / 不存在的目录")
    print("=" * 50)

    result = load_configs("/nonexistent/path/for/mcp/configs")
    assert len(result) == 0
    print("  PASSED\n")


def test_mcpclient_creation():
    print("=" * 50)
    print("Test 5: MCPClient 创建")
    print("=" * 50)

    config = MCPServerConfig(
        name="test-client",
        command="echo",
        args=["test"],
        env={},
    )
    client = MCPClient(config)
    assert client.name == "test-client"
    assert client.state == "inactive"
    print(f"  name: {client.name}, state: {client.state}")
    print("  PASSED\n")


async def test_mcpclient_start_and_close():
    print("=" * 50)
    print("Test 6: MCPClient start/close - 启动进程/关闭进程")
    print("=" * 50)

    config = MCPServerConfig(
        name="test-lifecycle",
        command="cat",
        args=[],
        env={},
    )
    client = MCPClient(config)
    await client.start()
    assert client.process is not None
    print(f"  process started, state: {client.state}")

    await client.close()
    assert client.state == "inactive"
    assert client.process is None
    print(f"  process closed, state: {client.state}")
    print("  PASSED\n")


async def main():
    print("\nMCP 模块功能测试\n")

    test_parse_single_server_format()
    test_parse_multi_server_format()
    test_load_configs_from_dir()
    test_load_configs_empty_dir()
    test_mcpclient_creation()
    await test_mcpclient_start_and_close()

    print("=" * 50)
    print("All tests PASSED!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
