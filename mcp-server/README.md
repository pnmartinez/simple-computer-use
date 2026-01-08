# LLM Control MCP Server

MCP server that allows Cursor to push updates to the LLM Control Flask server, which then delivers them to connected clients (e.g., Android app) via long polling.

## Tools Available

### `push_update`

Send an update/summary to the LLM Control server.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `summary` | string | ✅ | Human-readable summary of the changes |
| `changes` | string[] | ❌ | List of files changed |
| `type` | string | ❌ | Type of update (default: `cursor_update`) |

**Example:**
```
push_update({
  summary: "Añadida validación de email en login.py",
  changes: ["login.py", "validators.py"],
  type: "cursor_update"
})
```

### `check_server_status`

Check if the LLM Control server is running.

## Configuration

The server reads from environment variable:

- `LLM_CONTROL_HOST`: URL of the LLM Control server (default: `http://localhost:5000`)

## Installation

Already installed globally in Cursor at:
```
~/.cursor/mcp.json
```

## Development

```bash
# Install dependencies
npm install

# Build
npm run build

# Watch mode
npm run dev
```

## Flow

```
┌─────────┐       ┌──────────────────┐       ┌─────────────────┐
│ Cursor  │──────►│ llm-control-mcp  │──────►│ Flask Server    │
│ (agent) │ MCP   │ (this server)    │ HTTP  │ /push-update    │
└─────────┘       └──────────────────┘       └────────┬────────┘
                                                      │
                                                      ▼
                                             ┌─────────────────┐
                                             │ Android Client  │
                                             │ (long polling)  │
                                             └─────────────────┘
```
