"""Everything the agent does is reported as one of these events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class UserMessage:
    text: str


@dataclass(frozen=True)
class Thought:
    """Text the model writes while it is still working, before it uses a tool."""

    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call: ToolCall
    output: str  # the text the model reads
    is_error: bool = False
    data: Any = None  # the same result as Python data, for the web page


@dataclass(frozen=True)
class ApprovalRequest:
    """The agent is paused until the user approves or declines this tool call."""

    call: ToolCall


@dataclass(frozen=True)
class Decision:
    call: ToolCall
    approved: bool


@dataclass(frozen=True)
class Answer:
    text: str


@dataclass(frozen=True)
class Stopped:
    """The agent stopped before it could answer, e.g. step limit or connection error."""

    reason: str


Event = UserMessage | Thought | ToolCall | ToolResult | ApprovalRequest | Decision | Answer | Stopped
