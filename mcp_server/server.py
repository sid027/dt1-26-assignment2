"""YOUR WORK: the tools your agent can use.

These example tools make a small holiday planner. Replace them with tools for your own
use case. The model only sees each tool's name, docstring and parameter descriptions,
so write them carefully: they decide when and how the agent uses a tool.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP("Holiday planner tools")

PLANS = Path(os.getenv("DATA_DIR", "data")) / "plans.json"
HEADERS = {"User-Agent": "dt1-26-assignment2 (https://github.com/sid027/dt1-26-assignment2)"}
WEATHER = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 80: "showers", 81: "showers", 82: "heavy showers",
    95: "thunderstorm", 96: "thunderstorm", 99: "thunderstorm",
}
City = Annotated[str, Field(description="City or town, e.g. 'Lucerne'")]
_lock = threading.Lock()


def get_json(url: str, **params: Any) -> dict:
    """Call a free web API. Errors become ToolErrors, which the agent sees and can react to."""
    try:
        response = httpx.get(url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise ToolError(f"The service did not answer: {error}") from error
    return response.json()


def locate(city: str) -> dict:
    found = get_json("https://geocoding-api.open-meteo.com/v1/search", name=city, count=1).get("results")
    if not found:
        raise ToolError(f"No place called '{city}' was found.")
    return found[0]


def load_plans() -> list[dict]:
    return json.loads(PLANS.read_text(encoding="utf-8")) if PLANS.exists() else []


@mcp.tool(annotations={"readOnlyHint": True})
def get_weather_forecast(
    city: City,
    days: Annotated[int, Field(ge=1, le=7, description="Number of days, starting today")] = 3,
) -> dict:
    """Daily weather forecast for a place: conditions, temperatures and chance of rain."""
    place = locate(city)
    daily = get_json(
        "https://api.open-meteo.com/v1/forecast",
        latitude=place["latitude"],
        longitude=place["longitude"],
        daily="weather_code,temperature_2m_min,temperature_2m_max,precipitation_probability_max",
        forecast_days=days,
        timezone="auto",
    )["daily"]
    rows = zip(daily["time"], daily["weather_code"], daily["temperature_2m_min"],
               daily["temperature_2m_max"], daily["precipitation_probability_max"])
    return {
        "place": f"{place['name']}, {place.get('country', '')}",
        "days": [
            {"date": day, "weather": WEATHER.get(code, "unknown"), "min_c": low, "max_c": high, "rain_chance_pct": rain}
            for day, code, low, high, rain in rows
        ],
    }


@mcp.tool(annotations={"readOnlyHint": True})
def find_sights(
    city: City,
    limit: Annotated[int, Field(ge=1, le=20, description="Maximum number of results")] = 10,
) -> list[dict]:
    """Places with a Wikipedia article near a city (museums, churches, parks, ...), nearest first."""
    place = locate(city)
    pages = get_json(
        "https://en.wikipedia.org/w/api.php",
        action="query",
        list="geosearch",
        gscoord=f"{place['latitude']}|{place['longitude']}",
        gsradius=10_000,
        gslimit=limit,
        format="json",
    )["query"]["geosearch"]
    return [{"name": page["title"], "distance_m": round(page["dist"])} for page in pages]


@mcp.tool(annotations={"readOnlyHint": False})
def save_plan(
    title: Annotated[str, Field(description="Short title, e.g. 'Rainy Saturday in Lucerne'")],
    plan: Annotated[str, Field(description="The complete plan as text")],
) -> dict:
    """Save a finished plan so the user can find it later."""
    with _lock:
        plans = load_plans()
        entry = {"id": len(plans) + 1, "title": title, "plan": plan,
                 "saved_at": datetime.now().isoformat(timespec="minutes")}
        PLANS.parent.mkdir(parents=True, exist_ok=True)
        temporary = PLANS.with_suffix(".tmp")
        temporary.write_text(json.dumps(plans + [entry], indent=2, ensure_ascii=False), encoding="utf-8")
        temporary.replace(PLANS)  # never leaves a half-written file behind
    return {"saved": True, "id": entry["id"]}


@mcp.tool(annotations={"readOnlyHint": True})
def list_saved_plans() -> list[dict]:
    """All saved plans, newest first."""
    return load_plans()[::-1]


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")  # Docker uses this to know the server is up


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), show_banner=False)
