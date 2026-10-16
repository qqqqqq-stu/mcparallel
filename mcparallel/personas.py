"""人格原型库：手写 20（游戏/打工人/创作者/主播）+ 麦门16型（字母映射生成）
+ 麦门单品人格 10（由菜品五维标签矩阵实时推导）。

注意合规：所有命名与文案均为本项目原创；
不使用任何第三方 IP 角色、真实人物，也不复刻麦当劳官方 2024「产品人格」战役的
任何人格名称与文案（酸黄瓜型/薯条型/圆筒型等）。
"""
from __future__ import annotations

import json
import os

from .menu import _norm_name

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

UNIVERSE_ZH = {
    "product": "🍔 麦门单品人格",
    "game": "🎮 游戏战术",
    "worker": "💼 打工人",
    "mbti": "🧠 麦门16型",
    "creator": "🎬 创作者",
    "streamer": "🎤 主播风格",
}

# ---------- 麦门16型（映射生成，非 MBTI 官方题目/描述的复制） ----------

MBTI_PROFILES = {
    "INTJ": ("冷静架构师", "一切尽在计划之中"),
    "INTP": ("逻辑漫游者", "先问为什么，再问吃什么"),
    "ENTJ": ("雷霆指挥官", "目标明确，执行到位"),
    "ENTP": ("脑洞军师", "我有一个不成熟的小建议"),
    "INFJ": ("温柔洞察者", "你的心思，我大概知道"),
    "INFP": ("理想诗人", "这顿饭得有点诗意"),
    "ENFJ": ("全场气氛组", "吃什么不重要，一起吃才重要"),
    "ENFP": ("快乐永动机", "今天的快乐由我承包"),
    "ISTJ": ("秩序守卫者", "老规矩，还是那家店"),
    "ISFJ": ("可靠后盾", "你先点，剩下的我来"),
    "ESTJ": ("效率执行官", "吃饱，是为了更好地干活"),
    "ESFJ": ("暖心召集人", "都别抢，我来点，人人有份"),
    "ISTP": ("沉默巧手", "话不多，但吃得讲究"),
    "ISFP": ("随性生活家", "跟着感觉走"),
    "ESTP": ("行动派玩家", "先吃起来，问题路上解决"),
    "ESFP": ("舞台发光体", "开饭就是开场"),
}

# 字母对五维（口味偏好语义）的贡献（基准 5.0，叠加后收敛到 1-10）
LETTER_DELTAS = {
    "E": {"thrill": 1.5},
    "I": {"refine": 1.5},
    "S": {"value": 1.0, "steady": 1.0},
    "N": {"refine": 1.5},
    "T": {"value": 1.5},
    "F": {"thrill": 0.5, "refine": 1.0},
    "J": {"steady": 1.5},
    "P": {"thrill": 1.0},
}


def _gen_mbti() -> list[dict]:
    personas = []
    for code, (nick, tagline) in MBTI_PROFILES.items():
        vec = {d: 5.0 for d in ("thrill", "sustain", "value", "refine", "steady")}
        for letter in code:
            for dim, delta in LETTER_DELTAS[letter].items():
                vec[dim] += delta
        vec = {k: round(min(10.0, max(1.0, v)), 1) for k, v in vec.items()}
        personas.append(
            {
                "id": f"mbti-{code}",
                "universe": "mbti",
                "name": f"{code} · {nick}",
                "tagline": tagline,
                "vector": vec,
                "keywords": [f"{code[0]}型能量方向", f"{code[1]}型信息偏好", f"{code[2]}型决策风格", f"{code[3]}型生活节奏"],
                "style_note": "麦门16型为项目自研的轻量人格画像，仅供娱乐",
                "sample_line": tagline,
            }
        )
    return personas


# ---------- 单品人格（优先营养表推导，菜单只做价格补充） ----------
# 菜单按时段/季节轮换（宵夜档没有麦满分、甜品档变动大），而 160 条营养表稳定，
# 因此单品人格向量优先由营养数据推导；当前菜单命中时用真实价格修正性价比维。

PRODUCT_ALIASES = {
    "麦辣鸡腿汉堡": ["麦辣鸡腿堡"],
    "奥利奥麦旋风": ["麦旋风"],
    "朱古力新地": ["新地"],
    "猪柳麦满分": ["麦满分"],
    "拿铁": ["奶铁", "麦咖啡™奶铁"],
    "那么大鸡排": ["鸡排"],
}


def _find_menu_item(product: str, items: list[dict]) -> dict | None:
    from .menu import _norm_name

    names = [product] + PRODUCT_ALIASES.get(product, [])
    for want in names:
        target = _norm_name(want)
        for it in items:
            if _norm_name(it["name"]) == target:
                return it
    # 包含匹配（如「随心配」→「精选超值随心配」；「麦辣鸡翅」→「麦辣鸡翅4块套餐」）
    best = None
    for want in names:
        target = _norm_name(want)
        if len(target) < 2:
            continue
        for it in items:
            n = _norm_name(it["name"])
            if target in n or n in target:
                if best is None or len(n) < len(_norm_name(best["name"])):
                    best = it
    return best


def _find_nutrition_row(product: str, nutrition_rows: list[dict]) -> dict | None:
    from .menu import _norm_name

    names = [product] + PRODUCT_ALIASES.get(product, [])
    for want in names:
        target = _norm_name(want)
        for row in nutrition_rows:
            if _norm_name(row["name"]) == target:
                return row
    return None


def _sharpen(vec: dict, items: list[dict], factor: float = 1.35) -> dict:
    """锐化单品人格向量：偏离全菜单均值的方向放大。

    营养推导的向量天然偏向"中庸"（新地/麦旋风的营养数据都很平均），
    会变成谁都能匹配的磁铁；放大特征才能让甜品更像甜品、巨无霸更像巨无霸。
    """
    if not items:
        return vec
    import statistics

    from .tag_matrix import DIMS

    means = {d: statistics.fmean(it["vector"][d] for it in items) for d in DIMS}
    return {d: round(min(10.0, max(1.0, means[d] + factor * (vec[d] - means[d]))), 1) for d in DIMS}


def _derive_product_vector(cfg: dict, nutrition_rows: list[dict], items: list[dict]) -> dict:
    from .tag_matrix import compute_item_vector, guess_pool, population_stats

    # 1) 当前菜单命中 → 直接用菜单向量（含实时价格）
    mi = _find_menu_item(cfg["product"], items)
    if mi and mi.get("vector"):
        return _sharpen(dict(mi["vector"]), items)
    # 2) 营养表命中 → 营养推导（池按名称判断，性价比用兜底值）
    row = _find_nutrition_row(cfg["product"], nutrition_rows)
    if row:
        stats = population_stats(nutrition_rows)
        pool = guess_pool(cfg["product"]) if cfg["product"] not in ("巨无霸", "麦辣鸡腿汉堡", "猪柳麦满分") else "staple"
        vec = compute_item_vector(
            cfg["product"], pool, row, stats, fallback_value=cfg["fallback_vector"]["value"]
        )
        return _sharpen(vec, items)
    # 3) 完全无数据 → 配置兜底
    return _sharpen(dict(cfg["fallback_vector"]), items)


def _gen_product_personas(configs: list[dict], nutrition_rows: list[dict], items: list[dict]) -> list[dict]:
    personas = []
    for cfg in configs:
        vec = _derive_product_vector(cfg, nutrition_rows, items)
        personas.append(
            {
                "id": cfg["id"],
                "universe": "product",
                "name": cfg["name"],
                "tagline": cfg["tagline"],
                "vector": vec,
                "keywords": cfg["keywords"],
                "style_note": cfg["style_note"] + "；五维由真实营养/价格数据推导",
                "sample_line": cfg["sample_line"],
            }
        )
    return personas


# ---------- 汇总加载 ----------

def load_personas(items: list[dict], nutrition_rows: list[dict]) -> list[dict]:
    """items 为已 build_matrix 的菜品列表；nutrition_rows 为官方营养表（160 条）。"""
    with open(os.path.join(DATA_DIR, "personas.json"), encoding="utf-8") as f:
        raw = json.load(f)
    personas = [dict(p) for p in raw["personas"]]
    personas += _gen_product_personas(raw["product_personas"], nutrition_rows, items)
    personas += _gen_mbti()
    return personas
