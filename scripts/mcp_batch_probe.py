#!/usr/bin/env python3
"""Batch probe of McDonald's MCP server — READ-ONLY tools only.

Never calls state-changing tools (create-order, cancel-order, draw-lottery,
auto-bind-coupons, mall-create-order, party-order-create, delivery-create-address).

Each result is saved to docs/probe/call_<tool>.json.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp_probe import initialize, call_tool, load_token, PROBE_DIR

TOKEN = load_token()


def run(sid, name, args, save=True):
    status, result = call_tool(TOKEN, sid, name, args)
    if save:
        with open(os.path.join(PROBE_DIR, f"call_{name}.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    flag = "OK " if status == 200 and not result.get("error") else "ERR"
    print(f"[{flag}] {name}({json.dumps(args, ensure_ascii=False)}) HTTP {status}")
    return result


def content_of(result):
    """MCP tool results carry clean JSON in structuredContent.data; text is LLM-facing docs."""
    try:
        return result["result"]["structuredContent"]["data"]
    except (KeyError, TypeError):
        pass
    try:
        text = result["result"]["content"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        return None


def main():
    sid, _ = initialize(TOKEN)

    # Phase 1: no-arg read-only tools
    for tool in ["now-time-info", "list-nutrition-foods", "available-coupons",
                 "query-my-account", "query-lottery-info", "campaign-calendar",
                 "query-my-coupons", "order-list", "delivery-query-addresses",
                 "query-my-prizes"]:
        run(sid, tool, {})

    # Phase 2: store lookup with fallbacks
    stores = []
    for args in [
        {"beType": 1, "searchType": 2, "city": "上海市"},
        {"beType": 1, "searchType": 2, "city": "上海市", "keyword": "麦当劳"},
        {"beType": 1, "searchType": 1},
    ]:
        result = run(sid, "query-nearby-stores", args)
        data = content_of(result)
        if isinstance(data, dict):
            for key in ("stores", "storeList", "list", "data"):
                if isinstance(data.get(key), list):
                    stores = data[key]
                    break
        elif isinstance(data, list):
            stores = data
        if stores:
            break
    print(f"\n--> got {len(stores)} stores; first store:")
    print(json.dumps(stores[0] if stores else {}, ensure_ascii=False, indent=2)[:800])

    if not stores:
        print("!! no store found; skipping store-dependent calls")
        return

    store_code = None
    for k in ("storeCode", "code", "storecode", "id"):
        if stores[0].get(k):
            store_code = str(stores[0][k])
            break
    be_code = stores[0].get("beCode")
    print(f"\n--> storeCode={store_code} beCode={be_code}")

    # Phase 3: store-dependent tools (到店自提 beType=1, orderType=1, no beCode)
    meals_args = {"storeCode": store_code, "orderType": 1, "beType": 1}
    if be_code:
        meals_args["beCode"] = be_code
    meals = run(sid, "query-meals", meals_args)
    coupons = run(sid, "query-store-coupons", {"storeCode": store_code, "orderType": 1, "beType": 1})

    # Summarize menu shape
    mdata = content_of(meals)
    if isinstance(mdata, dict):
        print("\n--> query-meals top-level keys:", list(mdata.keys()))
        for k, v in mdata.items():
            if isinstance(v, list):
                print(f"    {k}: list[{len(v)}]", json.dumps(v[0], ensure_ascii=False)[:300] if v else "")
    print("\nDone. Raw results in docs/probe/")


if __name__ == "__main__":
    main()
