"""五维双向匹配引擎（确定性算法，纯标准库，可单测）。

正向：人格向量 → 最契合的菜品（TA 会吃什么）
逆向：用户口味向量（常点组合聚合 / 场景题作答）→ 最契合的人格（你是谁）

相似度用「中心化余弦」（皮尔逊相关）：先减去全菜单基线再比夹角。
非负五维向量的普通余弦天然挤在高位（都被"公共中高分基线"淹没），
中心化后只比较偏离方向——巨无霸的高续航、麦辣的高刺激才是区分信号。
"""
from __future__ import annotations

import math
import statistics

from .tag_matrix import DIMS

DRAWABLE_POOLS = ("staple", "snack", "drink")


def baseline_from_items(items: list[dict]) -> dict:
    """全菜单五维均值，作为比较的公共基线。"""
    return {d: statistics.fmean(it["vector"][d] for it in items) for d in DIMS}


def centered_cosine(a: dict, b: dict, baseline: dict) -> float:
    """基线中心化后的余弦（夹角），负相关截断为 0（视为不契合）。"""
    ca = [a[d] - baseline[d] for d in DIMS]
    cb = [b[d] - baseline[d] for d in DIMS]
    dot = sum(x * y for x, y in zip(ca, cb))
    na = math.sqrt(sum(x * x for x in ca))
    nb = math.sqrt(sum(y * y for y in cb))
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, dot / (na * nb))


def match_items(
    persona_vec: dict,
    items: list[dict],
    pool: str | None = None,
    top_n: int = 3,
    baseline: dict | None = None,
) -> list[dict]:
    """正向：给人格找最契合的菜品。pool 可限定 staple/snack/drink。"""
    baseline = baseline or baseline_from_items(items)
    cands = [it for it in items if it["pool"] in DRAWABLE_POOLS]
    if pool:
        cands = [it for it in cands if it["pool"] == pool]
    ranked = sorted(cands, key=lambda it: (-centered_cosine(persona_vec, it["vector"], baseline), it["price"]))
    return ranked[:top_n]


def taste_vector(chosen: list[dict], all_items: list[dict], amplify: float = 1.1) -> dict:
    """把用户常点组合聚合为口味五维向量。

    纯均值会被稀释成"中庸向量"（可乐把巨无霸的续航拉平），而常点组合的
    "人格"来自其中最突出的特征：先对全菜单做 z-score 放大偏离方向，
    再与各维最大值混合（0.6*max + 0.4*amplified_mean）。
    """
    if not chosen:
        raise ValueError("常点组合为空，无法聚合口味向量")
    means = {d: statistics.fmean(it["vector"][d] for it in all_items) for d in DIMS}
    stds = {d: statistics.pstdev([it["vector"][d] for it in all_items]) or 1.0 for d in DIMS}
    out = {}
    for d in DIMS:
        z = statistics.fmean((it["vector"][d] - means[d]) / stds[d] for it in chosen)
        amplified = min(10.0, max(1.0, means[d] + amplify * z * stds[d]))
        peak = max(it["vector"][d] for it in chosen)
        out[d] = round(0.6 * peak + 0.4 * amplified, 1)
    return out


def match_personas(
    user_vec: dict,
    personas: list[dict],
    items: list[dict],
    top_n: int = 3,
    universe: str | None = None,
    baseline: dict | None = None,
) -> list[tuple[dict, int]]:
    """逆向：给口味向量找最契合的人格，返回 (persona, 契合度%)。

    契合度 = 相对最优人格的比值缩放到 58-99（中心化相关本身区分度足够，
    直接线性映射会有大量 0 分，观感不佳）。
    """
    baseline = baseline or baseline_from_items(items)
    pool = [p for p in personas if p["universe"] == universe] if universe else personas
    scored = sorted(
        ((p, centered_cosine(user_vec, p["vector"], baseline)) for p in pool),
        key=lambda x: -x[1],
    )
    if not scored:
        return []
    best = scored[0][1]
    out = []
    for p, c in scored[:top_n]:
        fit = 99 if best <= 0 else round(58 + 41 * c / best)
        out.append((p, fit))
    return out
