import argparse
import json

import requests


def call_tool(
    session: requests.Session,
    url: str,
    tool_name: str,
    arguments: dict[str, object],
) -> requests.Response:
    body = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    response = session.post(
        url,
        json=body,
    )
    response.raise_for_status()
    return response


def main() -> None:
    parser = argparse.ArgumentParser(description="Check a Streamable HTTP MCP server.")
    parser.add_argument("--url", default="http://localhost:8000/mcp")
    parser.add_argument("--tool", help="Name of the MCP tool to call")
    parser.add_argument(
        "--arguments",
        default="{}",
        help='Tool arguments as a JSON object, for example \'{"days": 30}\'',
    )
    args = parser.parse_args()

    try:
        tool_arguments = json.loads(args.arguments)
    except json.JSONDecodeError as exc:
        parser.error(f"--arguments must be valid JSON: {exc}")
    if not isinstance(tool_arguments, dict):
        parser.error("--arguments must be a JSON object")

    session = requests.Session()
    session.headers.update(
        {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
    )

    response = session.post(
        args.url,
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "requests-test", "version": "1.0"},
            },
        },
    )
    response.raise_for_status()
    print("Initialize:", response.text)

    session_id = response.headers.get("MCP-Session-Id")
    if session_id:
        session.headers["MCP-Session-Id"] = session_id
    session.headers["MCP-Protocol-Version"] = "2025-03-26"

    response = session.post(
        args.url,
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    response.raise_for_status()

    response = session.post(
        args.url,
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        },
    )
    response.raise_for_status()
    print("Tools:", response.text)

    if args.tool:
        response = call_tool(session, args.url, args.tool, tool_arguments)
        print(f"Tool result ({args.tool}):", response.text)


if __name__ == "__main__":
    main()
