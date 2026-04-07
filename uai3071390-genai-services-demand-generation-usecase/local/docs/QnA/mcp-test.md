curl.exe -sk --% -X POST "https://dev-unitrisk.apps.gevernova.net/questionansweragent/api/assessments/test-assess-008/chat/reliability" -H "Content-Type: application/json" -d "{\"message\":\"Are the any ER cases for this unit that mention issues with getting the casing to align? - or casing bolts to tighten?\",\"context\":{\"serialNumber\":\"337X045\"}}"

# PowerShell / Windows curl.exe Commands for QnA Agent and MCP Endpoint Tests


## Quick Share: MCP Inspector Setup

Use this if someone asks how to set up and test the MCP server from their machine.

```text
To inspect the MCP server:

1. Install Node.js if `npx` is not available.
2. Launch MCP Inspector:
  npx -y @modelcontextprotocol/inspector
3. Open the local Inspector URL printed in the terminal.
4. In Inspector, select:
  - Transport Type: Streamable HTTP
  - URL: https://dev-unitrisk.apps.gevernova.net/dataservices/mcp/
5. If headers are needed, use:
  - Accept: application/json, text/event-stream
  - Content-Type: application/json

Important:
- Do not use STDIO for this server.
- A plain browser hit to the MCP URL is not a valid test.
- If Inspector fails with a TLS hostname mismatch, use the curl.exe -sk MCP initialize command as a fallback connectivity check.
- Current known issue: the deployed UAT hostname presents a certificate for a different hostname, so MCP Inspector may fail even when curl.exe -sk works.
```


## 1. QnA Agent Chat Endpoint (Public ALB)

### Multi-line (PowerShell script)
```powershell
curl.exe -sk -X POST "https://dev-unitrisk.apps.gevernova.net/questionansweragent/api/v1/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"Hello, what can you help me with?\",\"persona\":\"RE\",\"session_id\":\"test-deploy-001\"}"
```

### Single-line (easy copy-paste)
```powershell
curl.exe -sk -X POST "https://dev-unitrisk.apps.gevernova.net/questionansweragent/api/v1/chat" -H "Content-Type: application/json" -d "{\"prompt\":\"Hello, what can you help me with?\",\"persona\":\"RE\",\"session_id\":\"test-deploy-001\"}"
```


## 2. QnA Agent Chat Endpoint (Localhost)

### Multi-line (PowerShell script)
```powershell
curl.exe -s -X POST "http://localhost:8087/questionansweragent/api/v1/chat" ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\":\"Hello, what tools do you have available?\",\"persona\":\"RE\",\"session_id\":\"test-mcp-001\"}"
```

### Single-line (easy copy-paste)
```powershell
curl.exe -s -X POST "http://localhost:8087/questionansweragent/api/v1/chat" -H "Content-Type: application/json" -d "{\"prompt\":\"Hello, what tools do you have available?\",\"persona\":\"RE\",\"session_id\":\"test-mcp-001\"}"
```


## 3. MCP Direct Test (Initialize)

### Multi-line (PowerShell script)
```powershell
curl.exe -sk -X POST "https://dev-unitrisk.apps.gevernova.net/dataservices/mcp" ^
  -H "Content-Type: application/json" ^
  -H "Accept: application/json, text/event-stream" ^
  -d "{\"jsonrpc\":\"2.0\",\"id\":0,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-11-25\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"0.1\"}}}"
```

### Single-line (easy copy-paste)
```powershell
curl.exe -sk -X POST "https://dev-unitrisk.apps.gevernova.net/dataservices/mcp" -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -d "{\"jsonrpc\":\"2.0\",\"id\":0,\"method\":\"initialize\",\"params\":{\"protocolVersion\":\"2025-11-25\",\"capabilities\":{},\"clientInfo\":{\"name\":\"test\",\"version\":\"0.1\"}}}"
```


## 3A. MCP Inspector Setup (Verified Working — Mar 30 2026)

Use this when someone wants to inspect the MCP server interactively instead of using curl.

Source: https://github.com/modelcontextprotocol/inspector

### Prerequisites

- Windows laptop with Node.js installed (tested with Node v22.15.0, npm 10.9.2)
- Connected via Global Protector VPN
- PowerShell (not cmd) — but cmd works too if execution policy is not an issue

### Step 1: Verify Node.js

```powershell
node -v
```

If missing, install:

```powershell
winget install --id OpenJS.NodeJS.LTS -e --source winget --accept-package-agreements --accept-source-agreements
```

### Step 2: Fix PowerShell execution policy (if npx is blocked)

If `npx` gives `UnauthorizedAccess` / `running scripts is disabled`, either fix the policy:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Or bypass the .ps1 wrapper by using full paths (used throughout this guide):

```powershell
node "C:\Program Files\nodejs\node_modules\npm\bin\npx-cli.js" -v
node "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" config list
```

### Step 3: Configure npm proxy (one-time, required for GE network)

npm cannot reach registry.npmjs.org without the corporate proxy configured:

```powershell
node "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" config set proxy http://PITC-Zscaler-Americas-Alpharetta3PR.proxy.corporate.ge.com:80
node "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" config set https-proxy http://PITC-Zscaler-Americas-Alpharetta3PR.proxy.corporate.ge.com:80
```

Verify with:

```powershell
node "C:\Program Files\nodejs\node_modules\npm\bin\npm-cli.js" config list
```

You should see `https_proxy` and `proxy` in the output.

### Step 4: Launch MCP Inspector

Zscaler intercepts TLS and Node does not trust the Zscaler CA, so `NODE_TLS_REJECT_UNAUTHORIZED=0` is required:

```powershell
$env:NODE_TLS_REJECT_UNAUTHORIZED="0"; node "C:\Program Files\nodejs\node_modules\npm\bin\npx-cli.js" -y @modelcontextprotocol/inspector
```

Inspector will print a local URL:

```text
🚀 MCP Inspector is up and running at:
   http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=...
```

The browser should open automatically. If not, open the URL manually.

### Step 5: Connect to MCP server

In the Inspector browser UI:

| Field | Value |
|-------|-------|
| Transport Type | `Streamable HTTP` |
| URL | `https://dev-unitrisk.apps.gevernova.net/dataservices/mcp/` |
| Connection Type | `Via Proxy` |

Click **Connect**. You should see a green **Connected** dot and `data-tool-mcp Version: 2.14.4`.

### Step 6: Test tools

1. Click the **Tools** tab in the top nav bar.
2. Click **List Tools** — you should see all MCP tools listed.
3. Click any tool (e.g. `load_heatmap_dataservices_api_v1_heatmap_load_get`).
4. Fill in parameters (e.g. equipment_type: `GEN`, persona: `REL`, component: `ROTOR`).
5. Click **Run Tool** — you should see `Tool Result: Success` with data.

### Troubleshooting

| Error | Fix |
|-------|-----|
| `npx : running scripts is disabled` | Use full path: `node "C:\Program Files\nodejs\node_modules\npm\bin\npx-cli.js"` |
| `ETIMEDOUT` to registry.npmjs.org | Set npm proxy (Step 3) |
| `UNABLE_TO_GET_ISSUER_CERT_LOCALLY` | Set `$env:NODE_TLS_REJECT_UNAUTHORIZED="0"` before launching (Step 4) |
| `ENOTFOUND` wrong hostname | Manually set URL in Inspector UI to `https://dev-unitrisk.apps.gevernova.net/dataservices/mcp/` |
| Inspector opens but tools list is empty | Click **List Tools** button; check that URL ends with `/mcp/` (trailing slash) |

### Important notes

- Do not use `STDIO` transport — this MCP server runs remotely over HTTP.
- A plain browser visit to the MCP URL is not a valid test — the server expects MCP-compatible JSON-RPC.
- `curl.exe -sk` can be used as a fallback connectivity check (bypasses TLS).
- The `NODE_TLS_REJECT_UNAUTHORIZED=0` setting only affects the current PowerShell session.


## 4. Assessment Chat Example

### Multi-line (PowerShell script)
```powershell
curl.exe -sk -X POST "https://dev-unitrisk.apps.gevernova.net/questionansweragent/api/assessments/test-assess-008/chat/reliability" ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Are the any ER cases for this unit that mention issues with getting the casing to align? - or casing bolts to tighten?\",\"context\":{\"serialNumber\":\"337X045\"}}"
```

### Single-line (easy copy-paste)
```powershell
curl.exe -sk -X POST "https://dev-unitrisk.apps.gevernova.net/questionansweragent/api/assessments/test-assess-008/chat/reliability" -H "Content-Type: application/json" -d "{\"message\":\"Are the any ER cases for this unit that mention issues with getting the casing to align? - or casing bolts to tighten?\",\"context\":{\"serialNumber\":\"337X045\"}}"
```

---

# Notes

- Use these commands in PowerShell. The caret (^) is the line continuation character for Windows/PowerShell. If you want to run as a single line, just remove the carets and join the lines.
- For MCP, avoid trailing slashes to prevent POST-to-GET redirect issues.
- If authentication is required, add the necessary headers or tokens.
app-uai3071390-dev-sdg-dataservices

container

app-uai3071390-dev-sdg-questionansweragent:1
https://us-east-1.console.aws.amazon.com/ecs/v2/task-definitions/app-uai3071390-dev-sdg-questionansweragent/1/containers?region=us-east-1#

====

Invoke-RestMethod -Uri "https://dev-unitrisk.apps.gevernova.net/dataservices/mcp/dataservices" `
  -Method Post `
  -Headers @{
    "Content-Type" = "application/json"
    "Accept" = "application/json, text/event-stream"
  } `
  -Body '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"0.1"}}}'