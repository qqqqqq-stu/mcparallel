"""麦当劳 MCP 客户端：在线调用 + fixtures 离线回放双模式，纯标准库实现。

- 在线模式直连 https://mcp.mcd.cn（Streamable HTTP，Bearer Token）。
- 离线模式回放 fixtures/ 下录制的真实响应，无需 Token，用于零门槛演示。
- record=True 时在线结果自动写入 fixtures，用于刷新录制。
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES_DIR = os.path.join(ROOT, "fixtures")
MCP_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-03-26"


def _load_env_token():
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == "MCD_MCP_TOKEN":
                        return v.strip()
    return None


def fixture_key(tool: str, args: dict) -> str:
    if not args:
        return tool
    digest = hashlib.md5(json.dumps(args, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]
    return f"{tool}_{digest}"


# 仅这些工具允许"参数不同也回放任意录制"（结果与参数弱相关或仅作展示）。
# calculate-price / query-meal-detail 等结果强依赖参数的工具必须精确命中，
# 否则离线兜底会返回错误数据（例如把别的套餐价格当成这次的）。
FALLBACK_SAFE_TOOLS = {
    "query-meals",
    "list-nutrition-foods",
    "now-time-info",
    "campaign-calendar",
    "available-coupons",
    "query-nearby-stores",
    "query-store-coupons",
    "query-lottery-info",
}


def _parse_response(text: str) -> dict:
    """Streamable HTTP 可能返回纯 JSON 或单个 SSE 事件。"""
    datas = [l[5:].strip() for l in text.splitlines() if l.startswith("data:")]
    for candidate in ("\n".join(datas),) if datas else (text,):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return {"raw": text}


class MCPClient:
    def __init__(self, offline: bool = False, record: bool = False, token: str | None = None):
        self.offline = offline
        self.record = record
        self.token = token or os.environ.get("MCD_MCP_TOKEN") or _load_env_token()
        self._initialized = False

    def call(self, tool: str, args: dict | None = None):
        """调用工具，返回 structuredContent.data（纯 JSON 业务数据）。"""
        args = args or {}
        if self.offline:
            return self._replay(tool, args)
        data = self._rpc_call(tool, args)
        if self.record:
            self._save_fixture(tool, args, data)
        return data

    # ---------- fixtures 离线回放 ----------

    def _replay(self, tool, args):
        exact = os.path.join(FIXTURES_DIR, f"{fixture_key(tool, args)}.json")
        if os.path.exists(exact):
            with open(exact, encoding="utf-8") as f:
                return json.load(f)["data"]
        if tool in FALLBACK_SAFE_TOOLS and os.path.isdir(FIXTURES_DIR):
            for fname in sorted(os.listdir(FIXTURES_DIR)):
                if fname == f"{tool}.json" or fname.startswith(f"{tool}_"):
                    with open(os.path.join(FIXTURES_DIR, fname), encoding="utf-8") as f:
                        return json.load(f)["data"]
        raise FileNotFoundError(f"fixtures 中没有工具 {tool} 的精确录制（离线模式无法调用 MCP）")

    def _save_fixture(self, tool, args, data):
        os.makedirs(FIXTURES_DIR, exist_ok=True)
        path = os.path.join(FIXTURES_DIR, f"{fixture_key(tool, args)}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"tool": tool, "args": args, "data": data}, f, ensure_ascii=False, indent=2)

    # ---------- 在线 JSON-RPC ----------

    def _post(self, payload: dict):
        req = urllib.request.Request(MCP_URL, method="POST", data=json.dumps(payload).encode("utf-8"))
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"MCP HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from e

    def _ensure_init(self):
        if self._initialized:
            return
        init = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "mcparallel", "version": "0.1.0"},
            },
        }
        status, text = self._post(init)
        if status != 200:
            raise RuntimeError(f"MCP initialize 失败: {text[:200]}")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self._initialized = True

    def _rpc_call(self, tool, args):
        self._ensure_init()
        status, text = self._post(
            {"jsonrpc": "2.0", "id": 99, "method": "tools/call", "params": {"name": tool, "arguments": args}}
        )
        result = _parse_response(text)
        if status != 200 or result.get("error"):
            raise RuntimeError(f"tools/call {tool} 失败: {text[:300]}")
        sc = result.get("result", {}).get("structuredContent", {})
        if "data" in sc:
            return sc["data"]
        if sc.get("success") is False:
            raise RuntimeError(f"工具 {tool} 业务失败: {sc}")
        return sc
