"""板块一 · 三连抽：主食/小吃/饮品三池各抽一张，组成今日一餐。

- 已鉴定用户按人格向量加权抽取（人格贯穿三层的咬合机制之一）
- 卡背场景签（纯生活场景娱乐，无任何占卜释义）
"""
from __future__ import annotations

import random

from .matching import baseline_from_items, centered_cosine
from .menu import POOL_ZH
from .tag_matrix import DIMS

# 场景签：纯娱乐的生活场景调味，不预测未来、不解读命运
SCENES = [
    {"name": "开工运", "copy": "新的一天，先把胃填满，再填 KPI。"},
    {"name": "摸鱼运", "copy": "忙里偷的十五分钟，吃的就是比平时香。"},
    {"name": "聚餐运", "copy": "快乐是大家的，薯条是你抢到的。"},
    {"name": "夜宵运", "copy": "夜色配炸鸡，今天到此为止。"},
    {"name": "天降甜筒", "copy": "没什么道理，甜就是正义。"},
    {"name": "觉醒时刻", "copy": "有些灵感，是蘸着番茄酱来的。"},
]


def draw_three(
    items: list[dict],
    persona_vec: dict | None = None,
    seed: int | None = None,
) -> dict:
    """抽三张牌：主食/小吃/饮品各一张。返回 {scene, picks}。

    persona_vec 为空时均匀随机；有则用中心化相关加权——
    契合度可以为 0（负相关截断），因此人人都有抽到全池的机会。
    """
    rng = random.Random(seed)
    pools = {p: [it for it in items if it["pool"] == p] for p in ("staple", "snack", "drink")}
    if any(not v for v in pools.values()):
        raise ValueError("三池存在空池，无法抽取")

    baseline = baseline_from_items(items)
    picks = {}
    for pool_name, pool_items in pools.items():
        if persona_vec:
            # 池内余弦归一化后平方锐化：契合最高的单品权重约为中游的 3 倍、
            # 池底的 20 倍——人格偏好明显可见，但全池始终有机会（保留抽卡惊喜）。
            coses = [centered_cosine(persona_vec, it["vector"], baseline) for it in pool_items]
            c_min, c_max = min(coses), max(coses)
            span = c_max - c_min
            weights = [0.15 + 2.85 * (((c - c_min) / span) ** 2 if span > 1e-9 else 1.0) for c in coses]
        else:
            weights = None
        picks[pool_name] = rng.choices(pool_items, weights=weights, k=1)[0]

    return {"scene": dict(rng.choice(SCENES)), "picks": picks}


def draw_summary(result: dict) -> str:
    lines = [f"🎴 场景签：{result['scene']['name']} —— {result['scene']['copy']}"]
    total = 0.0
    for pool_name in ("staple", "snack", "drink"):
        it = result["picks"][pool_name]
        total += it["price"]
        lines.append(f"   [{POOL_ZH[pool_name]}] {it['name']}  ¥{it['price']}")
    lines.append(f"   直接单点合计：¥{round(total, 2)}")
    return "\n".join(lines)
