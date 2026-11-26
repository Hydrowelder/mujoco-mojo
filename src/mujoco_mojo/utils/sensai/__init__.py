"""
SensAI, the assistant in the Dojo and in Reloaded.

`agents/` has one module per agent, and `tools/` what their tools work out. This exports only what every agent shares: the model, the request cap and the tool-call trace. The agents are imported from their own modules, so that importing the docs agent (all Reloaded uses) does not load the Dojo, which the other agents read.
"""

import os

from mujoco_mojo.utils.log import quiet_in_terminal

from .model import build_fallback_model, usage_limits
from .tool_trace import CHAT_AGENT, ToolTrace

# pydantic-ai prints a banner to the terminal on its first run, which lands in the middle of Reloaded's log pane and the Dojo's console
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
# what SensAI's tools did and the HTTP requests to its models are for mojo.log: the Dojo shows the tool calls in the chat, and Reloaded only needs the answer
quiet_in_terminal(__name__)
quiet_in_terminal("httpx")
quiet_in_terminal("httpx2")

__all__ = [
    "CHAT_AGENT",
    "ToolTrace",
    "build_fallback_model",
    "usage_limits",
]
