"""The agent loop: ask the model, run the tools it picks, repeat until it answers."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from openai import OpenAI, OpenAIError

from . import events as ev
from .metrics import Pricing, Usage
from .settings import Settings
from .toolbox import Outcome, ToolBox

DECLINED = "The user declined this action. Do not try it again unless the user asks for it."
SKIPPED = "Not run, because the user sent a new message instead."


@dataclass
class Run:
    """One conversation. Keep it between page reloads; the agent continues where it stopped.

    A turn starts with each user message and lasts until the agent answers or stops.
    """

    messages: list[dict[str, Any]]
    events: list[ev.Event] = field(default_factory=list)
    queue: list[ev.ToolCall] = field(default_factory=list)  # requested, not yet run
    awaiting: ev.ToolCall | None = None  # paused until the user decides
    steps: int = 0
    turn: Usage = field(default_factory=Usage)  # restarts with every user message
    conversation: Usage = field(default_factory=Usage)


class Agent:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        llm: OpenAI | None = None,
        tools: ToolBox | None = None,
    ) -> None:
        self.settings = settings or Settings.load()
        self.llm = llm or OpenAI(base_url=self.settings.openrouter_url, api_key=self.settings.api_key)
        self.tools = tools or ToolBox(self.settings.mcp_server_url)
        self.pricing = Pricing(self.llm, self.settings.model)
        self.tools.refresh()
        if unknown := self.settings.approval_required - self.tools.names:
            raise ValueError(
                f"approval_required in config/agent.toml lists {sorted(unknown)}, "
                f"but the MCP server only has {sorted(self.tools.names)}."
            )

    def new_run(self) -> Run:
        today = date.today().strftime("%A, %d %B %Y")
        return Run(messages=[{"role": "system", "content": self.settings.system_prompt.replace("{today}", today)}])

    def send(self, run: Run, text: str) -> Iterator[ev.Event]:
        """Give the agent a new message and stream what it does."""
        if run.awaiting:  # the user moved on instead of deciding
            yield self._emit(run, ev.Decision(run.awaiting, approved=False))
            self._reply(run, run.awaiting, DECLINED)
            run.awaiting = None
        for call in run.queue:
            self._reply(run, call, SKIPPED)
        run.queue, run.steps, run.turn = [], 0, Usage()
        run.messages.append({"role": "user", "content": text})
        yield self._emit(run, ev.UserMessage(text))
        try:
            self.tools.refresh()  # picks up tools added since the page was opened
        except ConnectionError as error:
            yield self._emit(run, ev.Stopped(str(error)))
            return
        yield from self._loop(run)

    def decide(self, run: Run, approved: bool) -> Iterator[ev.Event]:
        """Approve or decline the paused tool call, then continue."""
        if (call := run.awaiting) is None:
            return
        run.awaiting = None
        yield self._emit(run, ev.Decision(call, approved))
        if approved:
            yield from self._execute(run, call)
        else:
            self._reply(run, call, DECLINED)
        yield from self._loop(run)

    # The loop -------------------------------------------------------------------------

    def _loop(self, run: Run) -> Iterator[ev.Event]:
        while True:
            while run.queue:
                call = run.queue.pop(0)
                if call.name in self.settings.approval_required:
                    run.awaiting = call
                    yield self._emit(run, ev.ApprovalRequest(call))
                    return
                yield from self._execute(run, call)

            if run.steps >= self.settings.max_steps:
                yield self._emit(run, ev.Stopped(f"Stopped after {run.steps} tool calls (max_steps)."))
                return
            try:
                message = self._ask_model(run)
            except OpenAIError as error:
                yield self._emit(run, ev.Stopped(f"The model could not be reached: {error}"))
                return

            if not message.tool_calls:
                run.messages.append({"role": "assistant", "content": message.content or ""})
                yield self._emit(run, ev.Answer(message.content or ""))
                return
            if message.content:
                yield self._emit(run, ev.Thought(message.content))
            run.messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                        for c in message.tool_calls
                    ],
                }
            )
            run.queue = [ev.ToolCall(c.id, c.function.name, _parse(c.function.arguments)) for c in message.tool_calls]

    def _ask_model(self, run: Run):
        tools = {"tools": self.tools.specs} if self.tools.specs else {}
        started = time.perf_counter()
        response = self.llm.chat.completions.create(
            model=self.settings.model,
            messages=run.messages,
            temperature=self.settings.temperature,
            **tools,
        )
        call = self.pricing.measure(response.usage, time.perf_counter() - started)
        run.turn.calls.append(call)
        run.conversation.calls.append(call)
        return response.choices[0].message

    def _execute(self, run: Run, call: ev.ToolCall) -> Iterator[ev.Event]:
        yield self._emit(run, call)
        if "_invalid_json" in call.arguments:
            outcome = Outcome("The arguments were not valid JSON. Try again.", is_error=True)
        else:
            outcome = self.tools.call(call.name, call.arguments)
        run.steps += 1
        self._reply(run, call, outcome.text)
        yield self._emit(run, ev.ToolResult(call, outcome.text, outcome.is_error, outcome.data))

    @staticmethod
    def _reply(run: Run, call: ev.ToolCall, content: str) -> None:
        run.messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    @staticmethod
    def _emit(run: Run, event: ev.Event) -> ev.Event:
        run.events.append(event)
        return event


def _parse(arguments: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"_invalid_json": arguments}
    return parsed if isinstance(parsed, dict) else {"_invalid_json": arguments}
