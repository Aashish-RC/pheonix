"""Tool Discovery, Dynamic Registration, and Execution Dispatcher."""

from typing import Any, Callable, Dict, List, Optional
import httpx

from .base import BaseTool, ToolContext, ToolResult
from .builtin import WebSearchTool, CalculatorTool, FileIOTool
from agent.core.manifest import ToolDefinition
from agent.core.exceptions import ToolExecutionError


class FunctionalTool(BaseTool):
    """Wrapper that adapts an arbitrary async or sync Python callable into a BaseTool."""

    def __init__(self, name: str, description: str, func: Callable, parameters_schema: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.func = func
        self.parameters_schema = parameters_schema or {}

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        import inspect
        import time
        start_time = time.perf_counter()
        try:
            if inspect.iscoroutinefunction(self.func):
                res = await self.func(params, context)
            else:
                res = self.func(params, context)

            if isinstance(res, ToolResult):
                return res

            return ToolResult(
                success=True,
                output=res,
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )


class RestApiTool(BaseTool):
    """Dynamically invokes an external REST endpoint as defined in the manifest."""

    def __init__(self, name: str, description: str, endpoint: str, parameters_schema: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.endpoint = endpoint
        self.parameters_schema = parameters_schema or {}

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        import time
        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(self.endpoint, json=params)
                resp.raise_for_status()
                data = resp.json()
            return ToolResult(
                success=True,
                output=data,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
                metadata={"endpoint": self.endpoint, "status_code": resp.status_code}
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"REST Tool execution error: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )


class ToolRegistry:
    """Central registry and factory for all executable agent tools."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        # Pre-register builtins
        self.register(WebSearchTool())
        self.register(CalculatorTool())
        self.register(FileIOTool())

    def register(self, tool: BaseTool) -> None:
        """Register a BaseTool instance."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[BaseTool]:
        """Return list of all registered tools."""
        return list(self._tools.values())

    def register_from_definition(self, tool_def: ToolDefinition, sandbox_runner: Optional[Any] = None) -> BaseTool:
        """Dynamically instantiate and register a tool from ToolDefinition."""
        if tool_def.name in self._tools:
            return self._tools[tool_def.name]

        if tool_def.type == "api" and tool_def.endpoint:
            tool = RestApiTool(
                name=tool_def.name,
                description=tool_def.description or f"API Tool calling {tool_def.endpoint}",
                endpoint=tool_def.endpoint,
                parameters_schema=tool_def.parameters or {},
            )
            self.register(tool)
            return tool

        elif tool_def.type == "sandbox_command":
            # Command execution in sandbox
            async def run_sandbox_cmd(params: Dict[str, Any], ctx: ToolContext):
                cmd = tool_def.command or params.get("command", "")
                if sandbox_runner:
                    return await sandbox_runner.run_command(cmd)
                return ToolResult(
                    success=True,
                    output=f"Simulated command execution: '{cmd}'",
                    metadata={"simulated": True}
                )

            tool = FunctionalTool(
                name=tool_def.name,
                description=tool_def.description or f"Execute sandbox command: {tool_def.command}",
                func=run_sandbox_cmd,
                parameters_schema=tool_def.parameters or {},
            )
            self.register(tool)
            return tool

        elif tool_def.type in ("mcp", "tools_mcp") or getattr(tool_def, "mcp_server", None):
            # Dedicated MCP tool routed through tools_mcp dispatcher
            async def run_mcp_tool(params: Dict[str, Any], ctx: ToolContext):
                try:
                    from tools_mcp.runner.dispatcher import ToolDispatcher
                    from tools_mcp.core.models import ToolInvocation
                    td = ToolDispatcher()
                    inv = ToolInvocation(tool_name=tool_def.name, arguments=params)
                    res = td.dispatch(inv)
                    return ToolResult(
                        success=res.success,
                        output=res.output,
                        error=res.error,
                        execution_time_ms=res.duration_ms,
                    )
                except Exception as e:
                    return ToolResult(
                        success=False,
                        output=None,
                        error=f"MCP tool '{tool_def.name}' error: {e}",
                    )

            tool = FunctionalTool(
                name=tool_def.name,
                description=tool_def.description or f"MCP tool {tool_def.name}",
                func=run_mcp_tool,
                parameters_schema=tool_def.parameters or {},
            )
            self.register(tool)
            return tool

        # Default fallback: check if tool is present in tools_mcp registry
        async def fallback_exec(params: Dict[str, Any], ctx: ToolContext):
            try:
                from tools_mcp.runner.dispatcher import ToolDispatcher
                from tools_mcp.core.models import ToolInvocation
                td = ToolDispatcher()
                if td.registry.get_tool(tool_def.name):
                    inv = ToolInvocation(tool_name=tool_def.name, arguments=params)
                    res = td.dispatch(inv)
                    return ToolResult(
                        success=res.success,
                        output=res.output,
                        error=res.error,
                        execution_time_ms=res.duration_ms,
                    )
            except Exception:
                pass
            return ToolResult(
                success=True,
                output=f"Executed tool {tool_def.name} with params {params}",
            )

        tool = FunctionalTool(
            name=tool_def.name,
            description=tool_def.description or f"Custom tool {tool_def.name}",
            func=fallback_exec,
            parameters_schema=tool_def.parameters or {},
        )
        self.register(tool)
        return tool


# Global default registry instance
default_tool_registry = ToolRegistry()
