"""Reads the agent's settings from config/ and the secrets from the environment."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # local runs; in Docker the variables come from compose.yaml


@dataclass(frozen=True)
class Settings:
    model: str
    system_prompt: str
    max_steps: int = 10
    temperature: float = 0.2
    approval_required: frozenset[str] = frozenset()
    mcp_server_url: str = "http://localhost:8000/mcp"
    openrouter_url: str = "https://openrouter.ai/api/v1"
    api_key: str = field(default="", repr=False)

    @classmethod
    def load(cls, config_dir: Path | None = None) -> Settings:
        config_dir = Path(config_dir or os.getenv("AGENT_CONFIG_DIR", ROOT / "config"))
        config = tomllib.loads((config_dir / "agent.toml").read_text(encoding="utf-8"))
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is missing. Put it in the .env file.")
        return cls(
            model=config["model"],
            system_prompt=_without_comments((config_dir / "system_prompt.md").read_text(encoding="utf-8")),
            max_steps=int(config.get("max_steps", cls.max_steps)),
            temperature=float(config.get("temperature", cls.temperature)),
            approval_required=frozenset(config.get("approval_required", [])),
            mcp_server_url=os.getenv("MCP_SERVER_URL", cls.mcp_server_url),
            api_key=api_key,
        )


def _without_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip()
