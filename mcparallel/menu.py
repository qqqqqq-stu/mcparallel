"""菜单加载、三池分类（主食/小吃/饮品）与官方营养数据关联。

数据全部来自麦当劳 MCP 的 query-meals / list-nutrition-foods 实时返回。
"""
from __future__ import annotations

from .mcp_client import MCPClient

DEFAULT_STORE = "1450713"  # fixtures 录制门店（上海·人民广场商圈）

# 官方 15 个分类 → 抽卡池
CATEGORY_POOL = {
    "鸡肉汉堡/卷": "staple",
    "巨无霸牛鱼肉堡": "staple",
    "安格斯MAX厚牛堡": "staple",
    "精选单人餐": "staple",
    "大堡口福单人餐": "staple",
    "500大卡套餐": "staple",
    "开心乐园": "staple",
    "小食拼盘/多人餐": "snack",
    "蘸酱炸鸡": "snack",
    "炸鸡": "snack",
    "小食甜品/其他": "snack",
    "麦咖啡": "drink",
    "饮品": "drink",
}
# 特殊分类：人气热卖=对主分类单品的重复引用；随心配1+1=组合 SKU（优惠引擎专用，不进抽卡池）
SPECIAL_CATEGORIES = {"人气热卖", "随心配1+1"}

POOL_ZH = {"staple": "主食", "snack": "小吃", "drink": "饮品", "combo": "随心配", "other": "非食品/周边"}

DRINK_HINTS = ("咖啡", "拿铁", "奶铁", "美式", "可乐", "雪碧", "茶", "奶昔", "汽水", "橙汁", "牛奶", "怡泉", "冰咖", "莫吉托", "轻乳", "柠檬水", "纯悦")
STAPLE_HINTS = ("堡", "卷", "麦满分", "三明治", "汉堡", "套餐")
# 非食品/周边（联名徽章、水手帽、玩具等）与酱料，不进抽卡池与匹配
NON_FOOD_KEYWORDS = ("徽章", "水手帽", "玩具", "贴纸")


def _is_non_food(name: str) -> bool:
    return name.endswith("酱") or any(k in name for k in NON_FOOD_KEYWORDS)


def _norm(s: str) -> str:
    return "".join(s.split())


def load_menu(client: MCPClient, store_code: str = DEFAULT_STORE) -> list[dict]:
    raw = client.call("query-meals", {"storeCode": store_code, "orderType": 1, "beType": 1})
    meals, categories = raw["meals"], raw["categories"]

    item_cats: dict[str, list[str]] = {}
    item_tags: dict[str, list[str]] = {}
    for c in categories:
        cname = _norm(c["name"])
        for m in c.get("meals", []):
            code = str(m["code"])
            item_cats.setdefault(code, []).append(cname)
            for t in m.get("tags") or []:
                item_tags.setdefault(code, []).append(t)

    items = []
    for code, m in meals.items():
        code = str(code)
        cats = item_cats.get(code, [])
        items.append(
            {
                "code": code,
                "name": m["name"],
                "price": float(m["currentPrice"]),
                "image": m.get("image", ""),
                "categories": cats,
                "tags": item_tags.get(code, []),
                "pool": _resolve_pool(cats, m["name"]),
            }
        )
    return items


def _resolve_pool(cats: list[str], name: str) -> str:
    if _is_non_food(name):
        return "other"
    for c in cats:
        if c == "随心配1+1":
            return "combo"
        if c in SPECIAL_CATEGORIES:
            continue
        if c in CATEGORY_POOL:
            return CATEGORY_POOL[c]
    if any(h in name for h in DRINK_HINTS):
        return "drink"
    if any(h in name for h in STAPLE_HINTS):
        return "staple"
    return "snack"


# ---------- 营养数据 ----------

import re as _re

_QUANTITY_RE = _re.compile(r"(\d+)\s*[块个]")  # 如「麦辣鸡翅4块」
_BRAND_PREFIXES = ("麦咖啡™", "麦咖啡", "【美汁源】")
_SIZE_WORDS = ("小", "中", "大")
# 套餐类命名 → 营养按「主品 + 中薯条 + 可乐中杯」估算（官方营养表只收录单品）
_COMBO_WORDS = ("套餐", "三件套", "四件套", "开心乐园餐", "随心选")
_COMBO_SIDES = ("中薯条", "可乐中杯")


def load_nutrition(client: MCPClient) -> list[dict]:
    """解析 list-nutrition-foods：MCP 返回的是逗号分隔文本表，不是 JSON 数组。

    格式：名称,说明,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium
    """
    data = client.call("list-nutrition-foods", {})
    rows = []
    for line in str(data).splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith("{"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 9 or not _is_num(parts[3]):
            continue
        try:
            rows.append(
                {
                    "name": parts[0],
                    "energy_kcal": float(parts[3]),
                    "protein": float(parts[4]),
                    "fat": float(parts[5]),
                    "carb": float(parts[6]),
                    "sodium": float(parts[7]),
                }
            )
        except ValueError:
            continue
    return rows


def _is_num(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _norm_name(s: str) -> str:
    return "".join(ch for ch in s if ch.isalnum())


_SUFFIXES = ("三件套", "两件套", "四件套", "套餐", "中杯", "大杯", "小杯", "(2块)", "（2块）", "-2块")


def _base_name(name: str) -> tuple[str, int | None]:
    """剥离规格后缀/品牌词/数量，返回 (基准名, 数量)。如「麦辣鸡翅4块」→("麦辣鸡翅", 4)。"""
    n = _norm_name(name)
    for brand in _BRAND_PREFIXES:
        nb = _norm_name(brand)
        if n.startswith(nb):
            n = n[len(nb):]
            break
    qty = None
    m = _QUANTITY_RE.search(name)
    if m:
        qty = int(m.group(1))
        n = _norm_name(_QUANTITY_RE.sub("", name))
        for brand in _BRAND_PREFIXES:
            nb = _norm_name(brand)
            if n.startswith(nb):
                n = n[len(nb):]
                break
    for suf in _SUFFIXES:
        ns = _norm_name(suf)
        if n.endswith(ns) and len(n) > len(ns):
            n = n[: -len(ns)]
            break
    return n, qty


def _scale_row(row: dict, name: str, scale: float) -> dict:
    if scale == 1.0:
        return row
    scaled = dict(row)
    for k in ("energy_kcal", "protein", "fat", "carb", "sodium"):
        scaled[k] = round(row[k] * scale, 1)
    scaled["name"] = name
    scaled["estimated"] = f"按 {row['name']} ×{scale:g} 换算"
    return scaled


def _match_size_family(name: str, nutrition_index: dict) -> dict | None:
    """规格族匹配：「雪碧」→「雪碧中杯」；「薯条」→「中薯条」。优先中杯。"""
    n = _norm_name(name)
    candidates = []
    for key, row in nutrition_index.items():
        if key == n:
            continue
        if key.startswith(n) and key.endswith("杯"):
            candidates.append(key)  # 后缀规格：雪碧中杯
        elif key.endswith(n) and key[:1] in _SIZE_WORDS and len(key) == len(n) + 1:
            candidates.append(key)  # 前缀规格：中薯条
    for pref in (n + "中杯", "中" + n):
        if pref in nutrition_index and pref in candidates:
            return nutrition_index[pref]
    if candidates:
        return nutrition_index[sorted(candidates, key=lambda k: (len(k), "中" not in k))[0]]
    return None


def _combo_estimate(row: dict, name: str, nutrition_index: dict) -> dict:
    """套餐类单品：主品 + 标准配餐（中薯条 + 可乐中杯）的标注式估算。"""
    sides = [nutrition_index[s] for s in _COMBO_SIDES if s in nutrition_index]
    if not sides:
        return row
    combined = dict(row)
    for k in ("energy_kcal", "protein", "fat", "carb", "sodium"):
        combined[k] = round(row[k] + sum(s[k] for s in sides), 1)
    combined["name"] = name
    combined["estimated"] = "套餐按主品+" + "+".join(_COMBO_SIDES) + "估算"
    return combined


def match_nutrition(name: str, nutrition_index: dict) -> dict | None:
    """菜单单品 → 营养行。策略：精确 → 后缀剥离 → 规格族 → 数量换算 → 包含（优选最短+中杯）。

    套餐类命名（套餐/三件套等）在命中主品后叠加标准配餐估算，并在
    `estimated` 字段标注换算口径——绝不冒充官方整餐数据。
    """
    n, qty = _base_name(name)
    # 1) 精确：官方营养表收录完整名称时直接使用；只命中剥离后主品、且是套餐命名时走估算
    full = _norm_name(name)
    if full in nutrition_index:
        return nutrition_index[full]
    if n in nutrition_index:
        base = nutrition_index[n]
        if any(w in name for w in _COMBO_WORDS):
            return _combo_estimate(base, name, nutrition_index)
        return base
    # 2) 规格族：雪碧/可乐/薯条/奶铁/美式
    hit = _match_size_family(n, nutrition_index) or _match_size_family(_norm_name(name), nutrition_index)
    if hit:
        return hit
    # 3) 数量换算：麦辣鸡翅4块 → 麦辣鸡翅-2块 ×2
    if qty:
        for key, row in nutrition_index.items():
            kb = _base_name(key)[0]
            if kb == n:
                base_qty = _QUANTITY_RE.search(key)
                scale = qty / int(base_qty.group(1)) if base_qty else 1.0
                scaled = _scale_row(row, name, max(scale, 0.25))
                if any(w in name for w in _COMBO_WORDS):
                    return _combo_estimate(scaled, name, nutrition_index)
                return scaled
    # 4) 前缀匹配：麦乐鸡 → 麦乐鸡5块（取最短规格）
    prefix_hits = [k for k in nutrition_index if k.startswith(n) and len(n) >= 3]
    if prefix_hits:
        base = nutrition_index[sorted(prefix_hits, key=len)[0]]
        if any(w in name for w in _COMBO_WORDS):
            return _combo_estimate(base, name, nutrition_index)
        return base
    # 5) 包含匹配：牛奶 → 热牛奶中杯（最短优先，其次含「中杯」）。
    #    菜单名至少 2 字才允许被包含——单字名（如「派」）无法区分香芋/菠萝，宁可不猜。
    contains = [k for k in nutrition_index if len(k) >= 3 and len(n) >= 2 and (k in n or n in k)]
    if contains:
        best = sorted(contains, key=lambda k: (len(k), "中杯" not in k))[0]
        return nutrition_index[best]
    return None


def attach_nutrition(items: list[dict], nutrition: list[dict]) -> list[dict]:
    idx = {_norm_name(r["name"]): r for r in nutrition}
    for it in items:
        it["nutrition"] = match_nutrition(it["name"], idx)
    return items
