# Era Bridge

Sits between **Era** (your Gemini/Google AI Studio assistant) and
**Era Local Agent**. You only ever talk to Era — Era calls Bridge,
and Bridge is the only thing that talks to Local Agent, entirely
through Local Agent's existing, unmodified HTTP API.

**Scope of this build (Phase 1 + 2, as approved):**
- Full session engine, parameter collection, and confirmation flow — built and tested.
- Automatic Local Agent detection, background startup, and health-check waiting — built and tested.
- Only the **5 commands Local Agent already supports over HTTP without parameters** (`open_notepad`, `open_calculator`, `open_file_explorer`, `open_chrome`, `open_camera`) execute end-to-end today.
- The other 7 commands return a clear `not_enabled` state — Phase 3 (an explicitly separate, approved change to Local Agent's `/execute` contract) is what would light these up. Nothing about them is broken or hidden; Bridge tells you plainly why.

**Nothing in this project modifies Era Local Agent.** Bridge only calls `GET /status` and `POST /execute` — the two endpoints Local Agent already exposes — or launches Local Agent's own existing start command as a subprocess when it isn't running.

## The "zero manual startup" behavior

You never need to open a terminal for either service. Every call to `/v1/execute` or `/v1/confirm`:

1. Checks whether Local Agent is already responding (`GET /status`, ~1.5s timeout).
2. If not, acquires a lock (so two near-simultaneous requests can't both try to launch it), re-checks in case another request just brought it up, then launches Local Agent's start command in the background — no visible console window.
3. Polls `/status` every 0.5s until it responds or a startup timeout (default 20s) is reached.
4. Only then proceeds with your actual command. If Local Agent still isn't up after the timeout, you get an honest `agent_unreachable` state — never a silent hang.

A PID file (`agent.pid`) records the process Bridge itself launched, so if Bridge is asked to ensure the Agent is running again shortly after, it recognizes "that process is already coming up" instead of launching a duplicate.

Bridge itself starts automatically at logon via Task Scheduler (see below) — so between that and the above, nothing needs a manual step.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. **Configure where your Local Agent project lives.** This wasn't part of the uploaded project, so Bridge doesn't assume a path — set it via environment variables (create a `.env` file, or set these in your shell/Task Scheduler action):

   ```
   AGENT_PROJECT_DIR=C:\path\to\your\era_agent
   AGENT_START_COMMAND=python -m uvicorn api_server:app --host 127.0.0.1 --port 8000
   BRIDGE_API_KEY=choose-a-fixed-secret-here
   ```

   If `AGENT_PROJECT_DIR` is left unset, auto-start is simply skipped (logged as a warning) — Bridge still works against an already-running Agent, it just can't launch it for you.

   If `BRIDGE_API_KEY` is left unset, Bridge generates a random one each restart and logs it — fine for a quick test, but set a fixed one before pointing Era's tool config at Bridge permanently.

## Running

Development (visible console):
```
python main.py
```

Production (no console window — what Task Scheduler uses):
```
run_bridge.pyw
```

Auto-start at logon:
```
python startup/install_task.py install
```
This registers a separate Task Scheduler entry (`EraBridgeService`) from whatever entry Local Agent might have — installing or removing one never affects the other. Uses `/RL LIMITED`, no admin prompt.

## API

Every route except `GET /v1/status` requires the header `X-Era-Bridge-Key: <your key>`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/status` | Bridge's own health, plus a live check of Local Agent (no auth) |
| GET | `/v1/commands` | Every command, its params, confirmation requirement, and whether it's `direct` (enabled) or `pending_agent_extension` |
| POST | `/v1/execute` | Start/continue a command conversation |
| POST | `/v1/confirm` | Confirm or cancel a command that returned `needs_confirmation` |
| GET | `/docs` | Swagger UI |

### Response states

`needs_input` · `needs_confirmation` · `success` · `failure` · `error` · `not_enabled` · `agent_unreachable` · `cancelled`

`not_enabled` and `agent_unreachable` are new in Bridge — `not_enabled` means the command exists on Local Agent but Bridge can't deliver its parameters yet (Phase 3); `agent_unreachable` means Bridge tried to reach and auto-start Local Agent and it didn't come up in time.

### Example — a working command

```
POST /v1/execute
{ "command": "open_notepad" }

-> { "state": "success", "session_id": "...", "message": "Notepad opened successfully.", "command": "open_notepad" }
```
If Local Agent wasn't already running, this same call transparently started it first — no separate step needed.

### Example — a not-yet-enabled command

```
POST /v1/execute
{ "command": "search_file" }

-> { "state": "not_enabled", "session_id": "...", "message": "'search_file' exists on Era Local Agent but isn't enabled through Era Bridge yet -- it needs an explicitly approved Local Agent update first (Phase 3).", "command": "search_file" }
```

## Tests

```
pip install -r requirements-dev.txt
pytest tests/ -v
```

28 tests, all passing in this environment: session engine logic (unknown/disabled/param-collection/confirmation transitions), session store persistence, the agent client's health-check and auto-start behavior (including the no-duplicate-process guarantee, tested directly against the PID-liveness check), and full API integration tests with a fake Agent standing in for the real one. A live end-to-end smoke test (Bridge + a minimal stand-in HTTP server playing Local Agent's role) was also run manually to confirm the real request/response cycle over the network, not just mocks.

## Project structure

```
era_bridge/
├── main.py                    # dev entry point (visible console)
├── run_bridge.pyw               # production entry point (windowless)
├── bridge_server.py              # FastAPI app assembly, lifespan startup check
├── config/
│   └── settings.py                # all configuration, env-driven, no hardcoded paths
├── core/
│   ├── logging_config.py           # rotating file + console logging
│   ├── session_store.py            # SQLite multi-turn conversation state (Bridge-side)
│   ├── command_catalog.py          # metadata for all 12 Local Agent commands; enabled flags
│   ├── session_engine.py           # pure state-machine logic (unit-testable, no I/O)
│   ├── agent_client.py             # HTTP client + auto-start/health-check/dedup logic
│   └── auth.py                      # API key dependency
├── api/
│   ├── routes_execute.py            # POST /v1/execute, POST /v1/confirm
│   └── routes_meta.py               # GET /v1/status, GET /v1/commands
├── startup/
│   └── install_task.py               # Task Scheduler registration for Bridge itself
├── tests/
├── requirements.txt
├── requirements-dev.txt
└── pytest.ini
```

## Phase 3 (not part of this build)

When you're ready, extending Local Agent's `POST /execute` to accept an
optional `params` field (additive, non-breaking to the 5 commands
that already work) plus a `/confirm`-equivalent is the only change
needed on the Agent side. On Bridge's side, flipping `enabled=True`
for the relevant entries in `core/command_catalog.py` is the only
change needed here — the session engine, parameter collection, and
confirmation flow already fully support them; they're just switched
off until that Local Agent change is separately approved and made.
