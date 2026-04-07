"""Minimal MCP client that connects to the data-service MCP server and lists available tools."""

import asyncio
import os

from fastmcp import Client

# MCP is mounted on the main data-service at /mcp
DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8086")
MCP_SERVER_URL = f"{DATA_SERVICE_URL.rstrip('/')}/dataservices/mcp"


async def main() -> None:
    async with Client(MCP_SERVER_URL) as client:
        tools = await client.list_tools()
        print(f"Discovered {len(tools)} tool(s):\n")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")


if __name__ == "__main__":
    asyncio.run(main())
