"""YOUR WORK: everything on the web page that belongs to your use case.

This is the only frontend file you need to change. app.py is generic: it shows the
conversation, every step of the agent, the approval buttons and the KPIs.
"""

from typing import Any

import streamlit as st

TITLE = "Holiday planner"
ICON = "🧭"
INTRO = "Tell me where you want to go. I check the weather, look for sights and can save your plan."
PLACEHOLDER = "Where do you want to go?"

# Example requests, shown as buttons on an empty page. They tell us what to test.
EXAMPLES = [
    "Plan a rain-proof Saturday in Lucerne.",
    "I have two days in Lugano. What should I do, given the weather?",
    "Which plans have I saved?",
]


# How the result of each tool is shown on the page. Each function receives the
# tool's result as Python data. Tools without a function here are shown as JSON.

def show_forecast(result: dict[str, Any]) -> None:
    st.caption(result["place"])
    st.dataframe(result["days"], hide_index=True)


def show_sights(result: list[dict[str, Any]]) -> None:
    st.markdown("\n".join(f"- {sight['name']} ({sight['distance_m']} m away)" for sight in result))


def show_plans(result: list[dict[str, Any]]) -> None:
    if not result:
        st.caption("No saved plans yet.")
    for plan in result:
        with st.container(border=True):
            st.markdown(f"**{plan['title']}**, saved {plan['saved_at']}")
            st.markdown(plan["plan"])


RESULT_VIEWS = {
    "get_weather_forecast": show_forecast,
    "find_sights": show_sights,
    "list_saved_plans": show_plans,
}
