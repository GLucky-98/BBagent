from fastapi import APIRouter

from backend.state import state_manager

router = APIRouter()


@router.get("")
async def list_tools():
    from BBagent.built_in_tool import TOOL_CREATOR
    from BBagent.built_in_tool.policy import Policy

    tools = []
    policy = Policy()
    for source, builder in TOOL_CREATOR.items():
        short_name = source.split(".")[-1] if "." in source else source
        try:
            import asyncio
            if asyncio.iscoroutinefunction(builder):
                tool = await builder(policy)
            else:
                tool = builder(policy)
            tools.append({
                "name": short_name,
                "displayName": tool.name,
                "source": source,
                "description": tool.description,
                "inputSchema": tool.input_schema or {},
            })
        except Exception:
            tools.append({
                "name": short_name,
                "displayName": short_name,
                "source": source,
                "description": "",
                "inputSchema": {},
            })

    for mcp_cfg in state_manager.mcp_servers:
        try:
            mcp_tools, client = await state_manager._create_mcp_client_for_agent(mcp_cfg.name)
            for tool in mcp_tools:
                tools.append({
                    "name": f"mcp:{mcp_cfg.name}",
                    "displayName": tool.name,
                    "source": f"mcp:{mcp_cfg.name}",
                    "description": tool.description,
                    "inputSchema": tool.input_schema or {},
                    "isMcp": True,
                    "mcpServerName": mcp_cfg.name,
                })
        except Exception:
            tools.append({
                "name": f"mcp:{mcp_cfg.name}",
                "displayName": f"MCP: {mcp_cfg.name}",
                "source": f"mcp:{mcp_cfg.name}",
                "description": f"MCP Server: {mcp_cfg.name} (offline)",
                "inputSchema": {},
                "isMcp": True,
                "mcpServerName": mcp_cfg.name,
            })

    return tools
