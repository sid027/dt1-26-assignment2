"""The web page. It is generic: you do not need to change this file.

Everything specific to your use case (title, examples, how tool results look) is in
use_case.py. This file shows the conversation, every step of the agent, the approval
buttons and the KPIs: the average cost and the average speed of the current turn.

Run it from the repository root:  python -m streamlit run frontend/app.py
"""

from collections.abc import Iterator

import pandas as pd
import streamlit as st

import use_case
from agent import Agent, events as ev

st.set_page_config(page_title=use_case.TITLE, page_icon=use_case.ICON)


@st.cache_resource(show_spinner="Connecting to the tools …")
def load_agent() -> Agent:
    return Agent()


try:
    agent = load_agent()
except Exception as error:
    st.error(f"The agent could not start. {error}")
    st.stop()

if "run" not in st.session_state:
    st.session_state.run = agent.new_run()  # one conversation per browser tab
run = st.session_state.run


# KPIs ---------------------------------------------------------------------------------

def usd(amount: float, digits: int = 5) -> str:
    return f"${amount:.{digits}f}"


def md(text: str) -> str:
    return text.replace("$", r"\$")  # in markdown, Streamlit reads $...$ as a formula


def show_kpis() -> None:
    """The KPIs of the current turn. A query is one request to the model; a turn has one or more."""
    turn, total, now = run.turn, run.conversation, run.turn.current
    current = {"delta_description": "current query", "delta_color": "off", "delta_arrow": "off", "border": True}
    with kpi_box.container():
        st.caption("This turn. Resets with every new message.")
        st.metric(
            "Average cost per query", usd(turn.average_cost) if now else "–", delta=usd(now.cost) if now else None,
            help="The mean cost of all queries in this turn, in USD.", **current,
        )
        st.metric(
            "Average speed per query", f"{turn.average_speed:.0f} tok/s" if now else "–",
            delta=f"{now.speed:.0f} tok/s" if now else None,
            help="The mean of the speeds of all queries in this turn, in output tokens per second.", **current,
        )
        if turn.calls:
            queries = pd.DataFrame(
                [{"#": number, "Tokens": call.tokens, "Cost": call.cost, "Speed": call.speed}
                 for number, call in enumerate(turn.calls, 1)]
            )
            last = len(queries) - 1
            highlight = lambda row: ["background-color: rgba(255, 75, 75, 0.2)" if row.name == last else ""] * len(row)
            st.dataframe(
                queries.style.apply(highlight, axis=1).format({"Tokens": "{:,}", "Cost": "${:.5f}", "Speed": "{:.0f} tok/s"}),
                hide_index=True,
            )
            st.caption("Queries of this turn. The highlighted row is the current query.")
        st.caption(md(f"Whole conversation: {len(total.calls)} queries · {total.tokens:,} tokens · {usd(total.cost)}"))


# Steps of the agent -------------------------------------------------------------------

def show(event: ev.Event) -> None:
    """Draw one step of the agent."""
    match event:
        case ev.Thought(text):
            st.caption(text)
        case ev.ToolCall(name=name, arguments=arguments):
            st.markdown(f"🔧 **{name}** " + ", ".join(f"`{key}={value!r}`" for key, value in arguments.items()))
        case ev.ToolResult(call=call, output=output, is_error=is_error, data=data):
            view = use_case.RESULT_VIEWS.get(call.name)
            title = "⚠️ The tool failed" if is_error else f"Result of {call.name}"
            with st.expander(title, expanded=is_error or view is not None):
                if view and not is_error and data is not None:
                    try:
                        view(data)
                    except Exception as error:  # a broken view must never break the page
                        st.warning(f"use_case.py could not show this result: {error!r}")
                        st.code(output, language="json", wrap_lines=True)
                else:
                    st.code(output, language="json", wrap_lines=True)
        case ev.ApprovalRequest(call):
            st.warning(f"✋ The agent wants to run **{call.name}**. Do you approve?")
            st.json(call.arguments)
        case ev.Decision(approved=approved):
            st.markdown("✅ Approved" if approved else "🚫 Declined")
        case ev.Answer(text):
            st.markdown(text)
        case ev.Stopped(reason):
            st.error(reason)


def show_history() -> None:
    bubble = None
    for event in run.events:
        if isinstance(event, ev.UserMessage):
            st.chat_message("user").markdown(event.text)
            bubble = st.chat_message("assistant")
        elif bubble:
            with bubble:
                show(event)


def stream(events: Iterator[ev.Event]) -> None:
    """Show new steps and KPIs while they happen, then redraw the page."""
    with st.chat_message("assistant"), st.spinner("Working …", show_time=True):
        for event in events:
            show(event)
            show_kpis()
    st.rerun()


def decide(approved: bool) -> None:
    st.session_state.decision = approved


# Page ---------------------------------------------------------------------------------

with st.sidebar:
    st.header("KPIs")
    kpi_box = st.empty()
    show_kpis()
    pricing = agent.pricing
    price = (f"  \nPrice per million tokens: {usd(pricing.input * 1e6, 2)} input · {usd(pricing.output * 1e6, 2)} output"
             if pricing.input is not None else "")
    st.caption(md(f"Model: {agent.settings.model}{price}"))
    if st.button("New conversation", width="stretch"):
        del st.session_state.run
        st.rerun()
    st.divider()
    st.header("Tools")
    for spec in agent.tools.specs:
        tool = spec["function"]
        lock = " 🔒" if tool["name"] in agent.settings.approval_required else ""
        st.markdown(f"**{tool['name']}**{lock}  \n{tool['description']}")
    st.caption("🔒 asks for approval first")

st.title(use_case.TITLE)
show_history()

if (decision := st.session_state.pop("decision", None)) is not None:
    stream(agent.decide(run, decision))

if run.awaiting:
    approve, decline = st.columns(2)
    approve.button("Approve", type="primary", width="stretch", on_click=decide, args=(True,))
    decline.button("Decline", width="stretch", on_click=decide, args=(False,))

prompt = st.chat_input(use_case.PLACEHOLDER, disabled=run.awaiting is not None)
if not run.events:
    st.markdown(use_case.INTRO)
    for example in use_case.EXAMPLES:
        if st.button(example, icon="💡", width="stretch"):
            prompt = example

if prompt:
    st.chat_message("user").markdown(prompt)
    stream(agent.send(run, prompt))
