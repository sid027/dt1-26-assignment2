# dt1-26-assignment2
Assignment 2 for DT1 @BFH Master Digital Administration. The assignment description is on Moodle.

## Directories

| Directory | Who works on it | What it is |
|---|---|---|
| `mcp_server/` | **You** | The tools your agent can use (FastMCP). Replace the example holiday-planner tools with your own. |
| `config/` | **You** | How your agent behaves: the model, its instructions in plain English, and which tools need the user's approval. |
| `frontend/` | **You**, only `use_case.py` | The web page (Streamlit) where users give the agent a goal and watch every step. |
| `agent/` | Provided, **do not change** | Runs the agent: sends the conversation to the model on OpenRouter, runs the tools it picks, and repeats until it answers. It also measures cost and speed. |

## Changing the web page

Change only `frontend/use_case.py`. It holds everything specific to your use case: the title, the intro text, the example requests and how each tool's result is shown.

`frontend/app.py` is generic and does not need changes. It shows the conversation, every step, the approval buttons and the KPIs in the sidebar:

- **Average cost per query**: the mean cost of the queries in the current turn, in USD.
- **Average speed per query**: the mean of the speeds of those queries, in output tokens per second.

A query is one request to the model. A turn starts with each new message and usually has several queries. "New conversation" resets everything.

## Installation

Copy `.env.example` to `.env` and add the OpenRouter key we give you.

**With Docker** (this is how we test your work):

```bash
docker compose up -d --build
```
*To Stop*
```bash
docker compose down
```

Then open http://localhost:8501.

**Without Docker** (for development, Python 3.11 or newer):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r agent/requirements.txt -r frontend/requirements.txt -r mcp_server/requirements.txt
```

Start the tools in one terminal and the web page in a second one, both from the repository root:

```bash
python mcp_server/server.py
python -m streamlit run frontend/app.py
```
