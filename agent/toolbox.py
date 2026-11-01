"""Connects the agent to the MCP server: lists its tools and calls them."""

from __future__ import annotations

import asyncio
import json
from typing import Any, NamedTuple

from fastmcp import Client

MAX_OUTPUT_CHARS = 8_000  # long tool outputs are cut, so one tool cannot flood the model


class Outcome(NamedTuple):
    text: str  # what the model reads
    is_error: bool = False
    data: Any = None  # the same result as Python data, for the web page


class ToolBox:
    def __init__(self, url: str, timeout: float = 30) -> None:
        self.url = url
        self.timeout = timeout
        self.specs: list[dict[str, Any]] = []

    @property
    def names(self) -> set[str]:
        return {spec["function"]["name"] for spec in self.specs}

    def refresh(self) -> list[dict[str, Any]]:
        """Fetch the tool list and convert it to the format the model expects."""
        try:
            tools = self._sync(self._list_tools())
        except Exception as error:
            raise ConnectionError(f"The MCP server at {self.url} is not reachable ({error}).") from error
        self.specs = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools
        ]
        return self.specs

    def call(self, name: str, arguments: dict[str, Any]) -> Outcome:
        """Run one tool. Failures are reported to the model, never raised."""
        if name not in self.names:
            return Outcome(f"There is no tool called '{name}'.", is_error=True)
        try:
            result = self._sync(self._call_tool(name, arguments))
        except Exception as error:  # server down, timeout, ...
            return Outcome(f"The tool server could not be reached: {error}", is_error=True)
        if result.structured_content is not None:
            output = json.dumps(result.structured_content, ensure_ascii=False, default=str)
        else:
            output = "\n".join(getattr(part, "text", str(part)) for part in result.content)
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + " … [output cut]"
        return Outcome(output, result.is_error, result.data)

    async def _list_tools(self):
        async with Client(self.url, timeout=self.timeout) as client:
            return await client.list_tools()

    async def _call_tool(self, name: str, arguments: dict[str, Any]):
        async with Client(self.url, timeout=self.timeout) as client:
            return await client.call_tool(name, arguments, raise_on_error=False)

    @staticmethod
    def _sync(coroutine):
        # One short connection per request keeps the agent synchronous and robust.
        return asyncio.run(coroutine)
