#!/usr/bin/env python3
"""从 docs/probe/ 的探测记录中提取非隐私响应，生成 fixtures/ 离线回放数据。

只提取公开业务数据（菜单/营养/算价/门店券/活动日历），
绝不复制含个人隐私的探测文件（订单/地址/积分/卡包/奖品）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from mcparallel.mcp_client import FIXTURES_DIR, fixture_key

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBE = os.path.join(ROOT, "docs", "probe")

# 探测文件 → (工具名, 当次调用参数)
SAFE_SOURCES = {
    "call_query-meals.json": ("query-meals", {"storeCode": "1450713", "orderType": 1, "beType": 1}),
    "call_list-nutrition-foods.json": ("list-nutrition-foods", {}),
    "call_query-meal-detail.json": ("query-meal-detail", {"storeCode": "1450713", "orderType": 1, "beType": 1, "code": "9900015568"}),
    "call_calculate-price.json": ("calculate-price", {"storeCode": "1450713", "orderType": 1, "beType": 1, "items": [{"productCode": "1100", "quantity": 1}]}),
    "call_query-store-coupons.json": ("query-store-coupons", {"storeCode": "1450713", "orderType": 1, "beType": 1}),
    "call_campaign-calendar.json": ("campaign-calendar", {}),
    "call_now-time-info.json": ("now-time-info", {}),
    "call_query-lottery-info.json": ("query-lottery-info", {}),
    # 注意：available-coupons / query-my-coupons / order-list / query-my-account /
    # delivery-query-addresses / query-my-prizes 含账号个人状态，一律不进 fixtures
}


def main():
    os.makedirs(FIXTURES_DIR, exist_ok=True)
    for fname, (tool, args) in SAFE_SOURCES.items():
        src = os.path.join(PROBE, fname)
        if not os.path.exists(src):
            print(f"跳过（探测文件不存在）: {fname}")
            continue
        with open(src, encoding="utf-8") as f:
            result = json.load(f)
        data = result["result"]["structuredContent"]["data"]
        out = os.path.join(FIXTURES_DIR, f"{fixture_key(tool, args)}.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"tool": tool, "args": args, "data": data}, f, ensure_ascii=False, indent=2)
        print(f"OK  {tool:<22} -> {os.path.basename(out)}")


if __name__ == "__main__":
    main()
