"""PROVIDED BY THE COURSE. Do not change the files in this directory.

The agent runs a loop: it sends the conversation to the model, runs the tools the
model asks for, sends back the results, and repeats until the model answers.
Every step is reported as an event, so the web page can show what the agent does.
"""

from . import events
from .core import Agent, Run
from .metrics import ModelCall, Usage
from .settings import Settings

__all__ = ["Agent", "ModelCall", "Run", "Settings", "Usage", "events"]
