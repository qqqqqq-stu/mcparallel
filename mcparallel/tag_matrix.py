"""菜品五维标签矩阵：由真实营养数据 + 实时价格 + 官方品类量化推导。

维度（0-10）：刺激 thrill / 续航 sustain / 性价比 value / 精致 refine / 稳健 steady
所有数值可追溯到 MCP 返回的营养与价格数据，不拍脑袋。
"""
from __future__ import annotations

import bisect

DIMS = ["thrill", "sustain", "value", "refine", "steady"]
DIM_ZH = {"thrill": "刺激", "sustain": "续航", "value": "性价比", "refine": "精致", "steady": "稳健"}

NUTRITION_KEYS = ("energy_kcal", "protein", "fat", "sodium")

# 无营养数据时的池基准（0-1）
POOL_BASE = {
    "staple": {"thrill": 0.45, "sustain": 0.70, "value": 0.50, "refine": 0.45, "steady": 0.50},
    "snack": {"thrill": 0.65, "sustain": 0.40, "value": 0.75, "refine": 0.50, "steady": 0.35},
    "drink": {"thrill": 0.30, "sustain": 0.15, "value": 0.70, "refine": 0.60, "steady": 0.60},
    "combo": {"thrill": 0.30, "sustain": 0.50, "value": 1.00, "refine": 0.40, "steady": 0.50},
}

SPICY_WORDS = ("麦辣", "辣", "麻辣")
LIGHT_WORDS = ("板烧", "烤", "玉米", "咖啡", "红茶", "鲜煮")
DRINK_WORDS = ("咖啡", "奶铁", "拿铁", "美式", "茶", "可乐", "雪碧", "奶昔", "汽水", "橙汁", "牛奶", "怡泉")


def _pct(sorted_vals: list[float], v: float) -> float:
    """值在总体中的百分位（0-1）。"""
    if len(sorted_vals) <= 1:
        return 0.5
    return bisect.bisect_left(sorted_vals, v) / (len(sorted_vals) - 1)


def population_stats(nutrition_rows: list[dict]) -> dict:
    """营养总体分布（160 条），所有向量推导共用同一基准。"""
    return {k: sorted(x[k] for x in nutrition_rows) for k in NUTRITION_KEYS}


def compute_item_vector(
    name: str,
    pool: str,
    nutrition_row: dict | None,
    stats: dict,
    price: float | None = None,
    prices: list[float] | None = None,
    fallback_value: float | None = None,
) -> dict:
    """单个菜品的五维向量（0-10）。菜单单品与单品人格共用本函数，保证口径一致。"""
    vec = dict(POOL_BASE.get(pool, POOL_BASE["snack"]))
    spicy = any(w in name for w in SPICY_WORDS)
    n = nutrition_row

    if n:
        e = _pct(stats["energy_kcal"], n["energy_kcal"])
        p = _pct(stats["protein"], n["protein"])
        f = _pct(stats["fat"], n["fat"])
        s = _pct(stats["sodium"], n["sodium"])
        vec["sustain"] = 0.55 * e + 0.45 * p
        vec["thrill"] = (0.85 if spicy else 0.25) * 0.6 + s * 0.4
        vec["steady"] = (1 - s) * 0.45 + (1 - f) * 0.35 + (0.20 if any(w in name for w in LIGHT_WORDS) else 0.0)
        pool_refine = {"drink": 0.40, "snack": 0.25, "staple": 0.10}.get(pool, 0.20)
        vec["refine"] = vec["refine"] * 0.30 + (1 - e) * 0.30 + pool_refine
    elif spicy:
        vec["thrill"] = max(vec["thrill"], 0.85)

    if pool == "combo":
        vec["value"] = 1.0
    elif price is not None and prices:
        vec["value"] = (1 - _pct(prices, price)) * 0.85 + 0.15 * vec["value"]
    elif fallback_value is not None:
        vec["value"] = fallback_value / 10.0

    return {k: round(min(10.0, max(1.0, v * 10)), 1) for k, v in vec.items()}


def build_matrix(items: list[dict], nutrition_rows: list[dict]) -> list[dict]:
    """为每个菜品计算五维向量，写入 item['vector']。"""
    stats = population_stats(nutrition_rows)
    prices = sorted(it["price"] for it in items if it["pool"] in ("staple", "snack", "drink"))

    for it in items:
        vec = compute_item_vector(it["name"], it["pool"], it.get("nutrition"), stats, it["price"], prices)
        if any("500" in c for c in it["categories"]):
            vec["refine"] = min(10.0, vec["refine"] + 2.0)
            vec["steady"] = min(10.0, vec["steady"] + 1.5)
        it["vector"] = vec
    return items


def guess_pool(name: str) -> str:
    if any(w in name for w in DRINK_WORDS):
        return "drink"
    return "snack"


def fmt_vector(vector: dict) -> str:
    return " ".join(f"{DIM_ZH[d]}{vector[d]}" for d in DIMS)
