from fastapi import APIRouter

from backend.state import state_manager

router = APIRouter()


@router.get("")
async def list_tools():
    """Return the list of ToolConfig blueprints.

    Per the unified-id design, each entry has:
      - id (UUID, the template_id)
      - name (display name; builtin shortName or MCP rawName)
      - source (built_in | mcp)
      - description
      - mcpServerId (for MCP tools)
      - mcpServerName (for MCP tools)

    The frontend uses `id` as the React key and to populate agent.toolIds.
    """
    return state_manager.list_tools()
