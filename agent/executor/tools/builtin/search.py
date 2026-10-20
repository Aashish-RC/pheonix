"""Built-in Web / Knowledge Search Tool."""

import time
from typing import Any, Dict
from ..base import BaseTool, ToolContext, ToolResult


class WebSearchTool(BaseTool):
    """Tool for simulating or executing web and knowledge searches."""

    name = "web_search"
    description = "Searches the web or knowledge base for information given a query."
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search keywords"},
            "num_results": {"type": "integer", "description": "Maximum results to retrieve", "default": 5}
        },
        "required": ["query"]
    }

    async def execute(self, params: Dict[str, Any], context: ToolContext) -> ToolResult:
        start_time = time.perf_counter()
        query = params.get("query", "").strip()
        num_results = params.get("num_results", 5)

        if not query:
            return ToolResult(
                success=False,
                output=None,
                error="Query cannot be empty",
                execution_time_ms=(time.perf_counter() - start_time) * 1000
            )

        # In production or test environments, returns structured search results
        results = [
            {
                "title": f"Result for '{query}' #{i+1}",
                "snippet": f"Synthetic snippet details and analysis for search topic: {query}",
                "url": f"https://example.org/search?q={query}&index={i+1}"
            }
            for i in range(min(num_results, 10))
        ]

        duration = (time.perf_counter() - start_time) * 1000
        return ToolResult(
            success=True,
            output=results,
            execution_time_ms=duration,
            metadata={"query": query, "count": len(results)}
        )
