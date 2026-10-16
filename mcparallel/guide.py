"""板块三 · 高性价比指南引擎：人群定制计算 + 预算搜索 + 指南长文生成。

所有结论由真实数据算出：营养表（160 条）驱动人群定制，
菜单实时价格驱动省钱数学，活动日历驱动时效提示。
"""
from __future__ import annotations

from .tag_matrix import DIMS

# ---------- 人群定制（营养数据驱动） ----------

def fitness_plan(nutrition_rows: list[dict]) -> dict:
    """健身人群：高碳日 / 低碳日 / 练后快充（按营养表排序，只看真实食物）。

    - 高碳日：碳水绝对量优先（含高碳水饮料，碳加载本就允许）
    - 低碳日：碳水 ≤40g 里挑蛋白质最高的（兼顾克制）
    - 练后快充：≤800 kcal 里挑蛋白质最高的（快充不是大餐）
    """
    real = [r for r in nutrition_rows if r["energy_kcal"] >= 200]
    return {
        "高碳日": [
            {"name": r["name"], "kcal": int(r["energy_kcal"]), "carb": r["carb"], "protein": r["protein"]}
            for r in sorted(real, key=lambda r: -r["carb"])[:8]
        ],
        "低碳日（高蛋白优先）": [
            {"name": r["name"], "kcal": int(r["energy_kcal"]), "carb": r["carb"], "protein": r["protein"]}
            for r in sorted([x for x in real if x["carb"] <= 40], key=lambda r: -r["protein"])[:8]
        ],
        "练后快充（蛋白+适度碳水）": [
            {"name": r["name"], "kcal": int(r["energy_kcal"]), "carb": r["carb"], "protein": r["protein"]}
            for r in sorted([x for x in real if x["energy_kcal"] <= 800], key=lambda r: -r["protein"])[:8]
        ],
    }


def fat_loss_list(nutrition_rows: list[dict], cap: int = 500) -> list[dict]:
    """减脂人群：≤cap 大卡的单品，按蛋白质密度排序（抗饿优先）。"""
    rows = [r for r in nutrition_rows if r["energy_kcal"] <= cap]
    rows.sort(key=lambda r: -(r["protein"] / max(r["energy_kcal"], 1)))
    return [
        {"name": r["name"], "kcal": r["energy_kcal"], "protein": r["protein"], "fat": r["fat"]} for r in rows[:12]
    ]


def kcal_per_yuan(items: list[dict]) -> list[dict]:
    """学生党核心指标：每元热量（仅统计已关联营养数据的单品）。"""
    rows = []
    for it in items:
        n = it.get("nutrition")
        if not n or it["price"] <= 0:
            continue
        rows.append(
            {
                "name": it["name"],
                "price": it["price"],
                "kcal": n["energy_kcal"],
                "kcal_per_yuan": round(n["energy_kcal"] / it["price"], 1),
            }
        )
    rows.sort(key=lambda r: -r["kcal_per_yuan"])
    return rows


def budget_search(items: list[dict], budget: float, min_kcal: int = 500) -> dict:
    """预算内吃饱方案：按每元热量贪心装填，返回组合与明细。"""
    ranked = kcal_per_yuan(items)
    picks, total_price, total_kcal = [], 0.0, 0
    for row in ranked:
        if total_price + row["price"] <= budget:
            picks.append(row)
            total_price += row["price"]
            total_kcal += row["kcal"]
        if total_price > budget - 3 or total_kcal >= min_kcal * 2:
            break
    return {
        "picks": picks,
        "total_price": round(total_price, 2),
        "total_kcal": total_kcal,
        "budget": budget,
        "enough": total_kcal >= min_kcal,
    }


def campaign_titles(client) -> list[str]:
    """当月活动日历标题（打工人时效提示）。"""
    try:
        data = client.call("campaign-calendar", {})
    except (RuntimeError, FileNotFoundError):
        return []
    titles = []
    for day in (data or {}).get("dailyList", []):
        for ev in day.get("events", []):
            article = ev.get("articleDto", {}) or {}
            t = article.get("highlights") or article.get("title") or ev.get("activityTitle") or ""
            if t and t not in titles:
                titles.append(f"{t}（{day.get('date', '')}）")
    return titles[:6]


# ---------- 专属省钱 tip（人格 × 指南挂接） ----------

_TIP_BY_DIM = {
    "value": "先在麦麦省把能领的券领了再下单；随心配 1+1 用主食配饮品是最稳的省钱底仓。",
    "thrill": "麦辣系列走 1+1 蓝区（麦香鸡/双层吉士可选），饮料换无糖可乐，刺激不减、钱包减负。",
    "sustain": "套餐比单品拆买便宜是结构性优惠：要吃饱直接点三件套，别单点汉堡+薯条+饮料。",
    "refine": "麦咖啡+甜品认准下午茶时段的限时券；想克制就选官方 500 大卡套餐，营养全透明。",
    "steady": "官方 500 大卡套餐就是为你准备的'清淡线'；板烧系列非油炸，是汉堡里的低负担选项。",
}


def persona_tip(persona: dict) -> str:
    top_dim = max(DIMS, key=lambda d: persona["vector"][d])
    return _TIP_BY_DIM[top_dim]
