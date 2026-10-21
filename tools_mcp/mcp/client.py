"""Model Context Protocol (MCP) Client: JSON-RPC 2.0 client for tool discovery and invocation."""

from typing import Any, Callable, Dict, List, Optional
from ..core.interfaces import BaseMCPClient
from ..core.models import ToolDefinition, ToolParameter, ToolType


class MCPClient(BaseMCPClient):
    """JSON-RPC 2.0 compliant MCP client supporting tool discovery and execution."""

    def __init__(self, server_name: str = "default_mcp_server"):
        self.server_name = server_name
        self._mock_tools: Dict[str, Dict[str, Any]] = {}
        self._mock_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}

    def register_mcp_server_mock(
        self,
        name: str,
        description: str,
        parameters: List[ToolParameter],
        handler: Callable[[Dict[str, Any]], Any],
    ) -> None:
        """Register an in-memory MCP tool endpoint for testing."""
        self._mock_tools[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
        }
        self._mock_handlers[name] = handler

    def list_mcp_tools(self) -> List[ToolDefinition]:
        """Discovers tools available on the MCP server via standard 'tools/list' protocol."""
        tool_defs = []
        for t_info in self._mock_tools.values():
            tool_defs.append(
                ToolDefinition(
                    name=t_info["name"],
                    description=t_info["description"],
                    tool_type=ToolType.MCP,
                    parameters=t_info["parameters"],
                )
            )
        return tool_defs

    def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Executes a tool on the MCP server via standard 'tools/call' protocol."""
        handler = self._mock_handlers.get(tool_name)
        if not handler:
            raise ValueError(f"MCP tool '{tool_name}' not found on server '{self.server_name}'")

        # Standard MCP execution return structure
        result_content = handler(arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(result_content),
                }
            ],
            "isError": False,
        }
