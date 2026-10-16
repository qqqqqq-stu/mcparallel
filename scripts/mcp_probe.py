#!/usr/bin/env python3
"""Probe McDonald's MCP server (https://mcp.mcd.cn) over Streamable HTTP.

Phase 1: initialize -> capture session id -> tools/list (with pagination).
Full raw output is saved to docs/probe/tools_list_raw.json.

Usage:
    python scripts/mcp_probe.py            # initialize + tools/list
    python scripts/mcp_probe.py call <tool_name> '<json_args>'
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "https://mcp.mcd.cn"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE_DIR = os.path.join(ROOT, "docs", "probe")
PROTOCOL_VERSIONS = ["2025-03-26", "2024-11-05"]


def load_token():
    with open(os.path.join(ROOT, ".env"), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()
    return os.environ["MCD_MCP_TOKEN"]


def post(payload, token, session_id=None):
    req = urllib.request.Request(BASE, method="POST", data=json.dumps(payload).encode("utf-8"))
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    if session_id:
        req.add_header("Mcp-Session-Id", session_id)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.headers.get("Mcp-Session-Id"), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, None, e.read().decode("utf-8", errors="replace")


def parse_response(text):
    """MCP streamable HTTP may answer with plain JSON or a single SSE event."""
    datas = [l[5:].strip() for l in text.splitlines() if l.startswith("data:")]
    if datas:
        try:
            return json.loads("\n".join(datas))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def initialize(token):
    for version in PROTOCOL_VERSIONS:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": version,
                "capabilities": {},
                "clientInfo": {"name": "mcparallel-probe", "version": "0.1.0"},
            },
        }
        status, sid, text = post(payload, token)
        result = parse_response(text)
        print(f"[initialize] protocol={version} HTTP {status} session={sid}")
        if status == 200 and "result" in result:
            # keep the session alive per spec
            post({"jsonrpc": "2.0", "method": "notifications/initialized"}, token, sid)
            return sid, result
        print(f"  -> {text[:500]}")
    raise SystemExit("initialize failed with all protocol versions")


def list_tools(token, sid):
    tools, cursor = [], None
    req_id = 10
    while True:
        params = {} if cursor is None else {"cursor": cursor}
        status, _, text = post({"jsonrpc": "2.0", "id": req_id, "method": "tools/list", "params": params}, token, sid)
        result = parse_response(text)
        if status != 200:
            raise SystemExit(f"tools/list failed: HTTP {status}: {text[:500]}")
        batch = result.get("result", {}).get("tools", [])
        tools.extend(batch)
        cursor = result.get("result", {}).get("nextCursor")
        req_id += 1
        if not cursor:
            break
    return tools


def call_tool(token, sid, name, args):
    status, _, text = post(
        {"jsonrpc": "2.0", "id": 99, "method": "tools/call", "params": {"name": name, "arguments": args}},
        token,
        sid,
    )
    return status, parse_response(text)


def main():
    os.makedirs(PROBE_DIR, exist_ok=True)
    token = load_token()

    if len(sys.argv) >= 4 and sys.argv[1] == "call":
        name, args = sys.argv[2], json.loads(sys.argv[3])
        sid, _ = initialize(token)
        status, result = call_tool(token, sid, name, args)
        out_path = os.path.join(PROBE_DIR, f"call_{name}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[tools/call {name}] HTTP {status} -> saved to {out_path}")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
        return

    sid, init_result = initialize(token)
    print(f"[server] {json.dumps(init_result.get('result', {}).get('serverInfo', {}), ensure_ascii=False)}")

    tools = list_tools(token, sid)
    with open(os.path.join(PROBE_DIR, "tools_list_raw.json"), "w", encoding="utf-8") as f:
        json.dump(tools, f, ensure_ascii=False, indent=2)

    print(f"\n[tools/list] {len(tools)} tools:")
    for t in tools:
        schema = t.get("inputSchema", {})
        props = schema.get("properties", {})
        required = schema.get("required", [])
        args_desc = ", ".join(
            f"{k}{'*' if k in required else ''}:{props[k].get('type', '?')}" for k in props
        )
        print(f"  - {t['name']}({args_desc})")
        desc = (t.get("description") or "").strip().replace("\n", " ")[:160]
        print(f"      {desc}")


if __name__ == "__main__":
    main()
