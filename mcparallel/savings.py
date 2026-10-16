"""板块一 · 最优购买方案引擎：对抽中的三件单品做三路径比价。

路径 A 直接单点：在线用 calculate-price 实算（含优惠），离线按菜单价估算并标注。
路径 B 1+1 随心配：任一单品命中随心配蓝区、另一单品命中粉区时，
       两件走随心配标价（实时菜单价，如 ¥13.9），其余单点。
路径 C 优惠券：列出当前门店可用券及有效期；叠加后的实付以下单核价为准
       （诚实边界：券路径不参与"最优"判定，只做提示）。
"""
from __future__ import annotations

from .mcp_client import MCPClient


class SavingsEngine:
    """items 传入已构建好的全量菜品列表（含 code/name/price/pool）。"""

    def __init__(self, client: MCPClient, items: list[dict], store_code: str):
        self.client = client
        self.items = items
        self.store_code = store_code
        self._zones: list[dict] | None = None

    # ---------- 1+1 蓝粉区 ----------

    def one_plus_one_zones(self) -> list[dict]:
        """解析门店所有随心配 SKU 的蓝区/粉区构成（来自 query-meal-detail 的 rounds）。

        注意：随心配子项的 code 与菜单单品 code 不一定是同一套体系
        （实测：菜单「可乐」9900008751 vs 粉区「可乐中杯」3050），
        因此同时记录 code 与名称，匹配时双轨比对。
        """
        if self._zones is not None:
            return self._zones
        zones = []
        for sku in [it for it in self.items if it["pool"] == "combo"]:
            try:
                detail = self.client.call(
                    "query-meal-detail",
                    {"storeCode": self.store_code, "orderType": 1, "beType": 1, "code": sku["code"]},
                )
            except (RuntimeError, FileNotFoundError):
                continue
            blue, pink = [], []
            for rnd in detail.get("rounds", []):
                bucket = blue if "蓝" in rnd.get("name", "") else pink
                for c in rnd.get("choices", []):
                    bucket.append({"code": str(c["code"]), "name": c["name"]})
            if blue and pink:
                zones.append({"sku": sku, "blue": blue, "pink": pink})
        self._zones = zones
        return zones

    # ---------- 三路径比价 ----------

    def evaluate(self, picks: list[dict]) -> dict:
        picks = list(picks)
        direct_total, source = self._price_direct(picks)
        plans = [
            {
                "key": "direct",
                "title": "直接单点",
                "total": direct_total,
                "detail": " + ".join(f"{it['name']} ¥{it['price']}" for it in picks),
                "source": source,
            }
        ]

        best_combo = None
        for zone in self.one_plus_one_zones():
            pair = self._find_pair(picks, zone)
            if not pair:
                continue
            rest = [it for it in picks if it not in pair]
            total = zone["sku"]["price"] + sum(it["price"] for it in rest)
            names = " + ".join(it["name"] for it in pair)
            desc = f"{zone['sku']['name']} ¥{zone['sku']['price']}（覆盖 {names}）"
            if rest:
                desc += " + " + " + ".join(f"{it['name']} ¥{it['price']}" for it in rest)
            if best_combo is None or total < best_combo["total"]:
                best_combo = {
                    "key": "one_plus_one",
                    "title": "1+1 随心配路径",
                    "total": total,
                    "detail": desc,
                    "source": "随心配标价 + 单点菜单价（以下单核价为准）",
                }
        if best_combo:
            plans.append(best_combo)

        # 券命中路径：券的适用单品命中抽取单品时，带券实算（未命中或离线无法核价则保持展示提示）
        coupon_plan = self._coupon_plan(picks)
        if coupon_plan:
            plans.append(coupon_plan)

        best = min(plans, key=lambda p: p["total"])
        return {
            "plans": plans,
            "coupons": self._coupon_notes(),
            "best": best,
            "saved": round(direct_total - best["total"], 2),
        }

    def _coupon_plan(self, picks: list[dict]) -> dict | None:
        """券适用单品命中时，全单直接购买 + 券带码实算。"""
        try:
            coupons = self.client.call(
                "query-store-coupons", {"storeCode": self.store_code, "orderType": 1, "beType": 1}
            ) or []
        except (RuntimeError, FileNotFoundError):
            return None
        pick_codes = {p["code"] for p in picks}
        for c in coupons:
            if not isinstance(c, dict):
                continue
            matched_code = None
            for prod in c.get("products", []) or []:
                if str(prod.get("productCode", "")) in pick_codes:
                    matched_code = str(prod["productCode"])
                    break
            if not matched_code:
                continue
            items_arg = [
                {
                    "productCode": p["code"],
                    "quantity": 1,
                    **(
                        {"couponId": c.get("couponId", ""), "couponCode": c.get("couponCode", "")}
                        if p["code"] == matched_code
                        else {}
                    ),
                }
                for p in picks
            ]
            try:
                data = self.client.call(
                    "calculate-price",
                    {"storeCode": self.store_code, "orderType": 1, "beType": 1, "items": items_arg},
                )
                price = data.get("price")
            except (RuntimeError, FileNotFoundError):
                continue
            if price is None:
                continue
            return {
                "key": "coupon",
                "title": f"用券「{c.get('title', '')}」",
                "total": round(price / 100, 2),
                "detail": "直接购买，券已带码计入实算（券为一次性资产，用前确认无需留作他用）",
                "source": "MCP calculate-price 实算（含券）",
            }
        return None

    def _find_pair(self, picks: list[dict], zone: dict) -> list[dict] | None:
        """找一对可被随心配覆盖的单品：一个在蓝区、另一个在粉区（code 或名称匹配）。"""
        for a in picks:
            for b in picks:
                if a is not b and self._in_zone(a, zone["blue"]) and self._in_zone(b, zone["pink"]):
                    return [a, b]
        return None

    @staticmethod
    def _in_zone(pick: dict, zone_choices: list[dict]) -> bool:
        def norm(s: str) -> str:
            return "".join(ch for ch in s if ch.isalnum())

        p_name = norm(pick["name"])
        for choice in zone_choices:
            if str(pick["code"]) == choice["code"]:
                return True
            c_name = norm(choice["name"])
            # 「可乐」→「可乐中杯」允许；「可乐」→「无糖可口可乐中杯」不允许（防止误配）
            if len(p_name) >= 2 and (c_name == p_name or c_name.startswith(p_name)):
                return True
        return False

    def _price_direct(self, picks: list[dict]) -> tuple[float, str]:
        """路径 A：在线 calculate-price 实算；离线按菜单价估算。"""
        items_arg = [{"productCode": it["code"], "quantity": 1} for it in picks]
        try:
            data = self.client.call(
                "calculate-price",
                {"storeCode": self.store_code, "orderType": 1, "beType": 1, "items": items_arg},
            )
            price = data.get("price")
            if price is not None:
                return round(price / 100, 2), "MCP calculate-price 实算"
        except (RuntimeError, FileNotFoundError):
            pass
        return round(sum(it["price"] for it in picks), 2), "菜单价估算（离线模式，未含折扣）"

    def _coupon_notes(self) -> list[dict]:
        try:
            coupons = self.client.call(
                "query-store-coupons", {"storeCode": self.store_code, "orderType": 1, "beType": 1}
            )
        except (RuntimeError, FileNotFoundError):
            return []
        return [
            {"title": c.get("title", ""), "valid": c.get("tradeDateTime", "")}
            for c in (coupons or [])
            if isinstance(c, dict)
        ][:5]


def savings_summary(result: dict) -> str:
    lines = []
    for plan in result["plans"]:
        tag = " ← 最优" if plan is result["best"] else ""
        lines.append(f"💰 [{plan['title']}] ¥{plan['total']}{tag}  （{plan['source']}）")
        lines.append(f"   {plan['detail']}")
    if result["saved"] > 0:
        lines.append(f"   → 共省 ¥{result['saved']}")
    for c in result["coupons"]:
        lines.append(f"🎫 可用券：{c['title']}（{c['valid']}，叠加实付以下单核价为准）")
    if not result["coupons"]:
        lines.append("🎫 当前门店暂无可提示的优惠券（以麦当劳 App 实时为准）")
    return "\n".join(lines)
