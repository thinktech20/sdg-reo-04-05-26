# MCP Architecture — Data Service & QnA Agent

## Protocol
- **MCP** = Model Context Protocol — JSON-RPC 2.0 over HTTP
- Transport: **streamable-http** (not SSE, not stdio)
- Single endpoint, stateful sessions via `Mcp-Session-Id` header

## Data Service (MCP Server)
- Mounted at **`/mcp`** in `data_service/main.py:185`: `app.mount("/mcp", mcp_starlette_app)`
- Internal Starlette sub-app with `Route("/")` → effective endpoint: `http://data-service:8086/mcp/`
- `server.py` docstring mentions old SSE mount — that's dead code, not active
- Tools exposed: `read_ibat`, `read_prism`, `load_risk_matrix`, retriever, ER, etc.

## QnA Agent (MCP Client)
- Uses Strands SDK `MCPClient` with `streamablehttp_client`
- Config: `MCP_SERVER_URL` auto-derived as `{DATA_SERVICE_URL}/mcp/`
- Transport built in `agent_factory.py:54`: `lambda: streamablehttp_client(config.MCP_SERVER_URL)`
- Per-request lifecycle: `MCPClient open → list tools → filter by persona → build agent → invoke → close`

## MCP JSON-RPC Flow

### 1. Initialize (POST `/mcp/`)
```json
{
  "jsonrpc": "2.0", "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": {"name": "qna-agent", "version": "1.0"}
  }
}
```
→ Server responds with capabilities + `Mcp-Session-Id` header

### 2. List Tools (POST `/mcp/` with session header)
```json
{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
```
→ Returns all available MCP tools

### 3. Call a Tool (POST `/mcp/` with session header)
```json
{
  "jsonrpc": "2.0", "id": 3,
  "method": "tools/call",
  "params": {"name": "read_ibat", "arguments": {"serial_number": "342447641"}}
}
```

## MCP vs REST
| Aspect       | REST API                          | MCP                                |
|-------------|-----------------------------------|-------------------------------------|
| Protocol    | HTTP verbs (GET/POST/PUT/DELETE)  | JSON-RPC 2.0 over POST             |
| Endpoints   | Multiple URLs (`/api/ibat`, etc.) | Single URL (`/mcp/`)               |
| Session     | Stateless                         | Stateful (`Mcp-Session-Id` header) |
| Discovery   | OpenAPI / Swagger                 | `tools/list` method                |

## Routing (nginx vs direct)
- **nginx** (browser → backend): `/dataservices/*` is an nginx proxy prefix, NOT a data-service path
  - `/api/*` → rewrites to `/dataservices/api/v1/*` → data-service:8086
  - `/dataservices/*` → pass-through → data-service:8086
  - `/qna/*` → rewrites to `/questionansweragent/*` → qna-agent:8087
- **Agent → data-service**: direct container-to-container, bypasses nginx
  - Correct path: `http://data-service:8086/mcp/`
  - WRONG path: `http://data-service:8086/dataservices/mcp/` (404)

## Testing MCP locally
```bash
# Start data-service (needs AWS creds + CA bundle for Zscaler)
cd backend/services/data-service
AWS_CA_BUNDLE=../../certs/ge-ca-bundle.pem PYTHONPATH=src:../../libs/commons/src \
  python -m uvicorn data_service.main:app --host 0.0.0.0 --port 8086

# Test MCP initialize
curl -s -X POST http://localhost:8086/mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

# Test via ALB (from PowerShell, not WSL due to Zscaler)
curl.exe -sk --% https://dev-unitrisk.apps.gevernova.net/dataservices/mcp/
```

# Note
No technical issue with MCP + REST on same container
MCP over streamable-http is just regular HTTP POST with JSON-RPC payloads. At the network level, it's indistinguishable from REST — same TCP, same port, same TLS. FastAPI mounts the MCP Starlette sub-app at /mcp alongside REST routes. They coexist perfectly fine. This is the standard pattern.

