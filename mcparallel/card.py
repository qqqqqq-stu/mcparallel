"""板块二 · 麦门身份卡渲染器：纯标准库 SVG 输出（GitHub 原生可渲染，利于传播）。

1200×1600，暗色潮牌风 + 麦当劳红金配色；
含五维雷达图（用户口味向量 vs 人格向量叠加）、口味条形、适配套餐、专属省钱 tip、推荐文案。
"""
from __future__ import annotations

import html
import math
import os
import time

from .tag_matrix import DIMS, DIM_ZH

W, H = 1200, 1680
RED, GOLD, BG, PANEL, TEXT, SUB = "#DA291C", "#FFC72C", "#15151f", "#1f1f2e", "#f5f5f7", "#a8a8b3"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "cards")


def _esc(s: str) -> str:
    return html.escape(str(s), quote=True)


def _radar_points(cx: float, cy: float, r: float, vector: dict) -> str:
    pts = []
    for i, d in enumerate(DIMS):
        angle = math.radians(-90 + i * 72)
        rr = r * (vector[d] / 10.0)
        pts.append(f"{cx + rr * math.cos(angle):.1f},{cy + rr * math.sin(angle):.1f}")
    return " ".join(pts)


def _radar_svg(cx: float, cy: float, r: float, user_vec: dict, persona_vec: dict) -> str:
    parts = []
    # 同心五边形网格（2/4/6/8/10）
    for level in (2, 4, 6, 8, 10):
        grid_vec = {d: level for d in DIMS}
        parts.append(
            f'<polygon points="{_radar_points(cx, cy, r, grid_vec)}" fill="none" stroke="#3a3a4e" stroke-width="1"/>'
        )
    # 轴线 + 维度标签
    for i, d in enumerate(DIMS):
        angle = math.radians(-90 + i * 72)
        lx, ly = cx + (r + 34) * math.cos(angle), cy + (r + 34) * math.sin(angle)
        parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{cx + r * math.cos(angle):.1f}" y2="{cy + r * math.sin(angle):.1f}" '
            f'stroke="#3a3a4e" stroke-width="1"/>'
        )
        anchor = "middle"
        if math.cos(angle) > 0.3:
            anchor = "start"
        elif math.cos(angle) < -0.3:
            anchor = "end"
        parts.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{SUB}" font-size="22" text-anchor="{anchor}" '
            f'dominant-baseline="middle">{DIM_ZH[d]}</text>'
        )
    # 人格向量（红虚线）与用户口味向量（金色填充）
    parts.append(
        f'<polygon points="{_radar_points(cx, cy, r, persona_vec)}" fill="none" stroke="{RED}" '
        f'stroke-width="2.5" stroke-dasharray="7 5"/>'
    )
    parts.append(
        f'<polygon points="{_radar_points(cx, cy, r, user_vec)}" fill="{GOLD}" fill-opacity="0.28" '
        f'stroke="{GOLD}" stroke-width="3"/>'
    )
    return "".join(parts)


def _bars_svg(x: float, y: float, w: float, vector: dict) -> str:
    parts = []
    for i, d in enumerate(DIMS):
        by = y + i * 40
        parts.append(f'<text x="{x}" y="{by + 18}" fill="{TEXT}" font-size="20">{DIM_ZH[d]}</text>')
        parts.append(f'<rect x="{x + 60}" y="{by + 4}" width="{w - 60}" height="16" rx="8" fill="#2c2c40"/>')
        bw = (w - 60) * (vector[d] / 10.0)
        parts.append(f'<rect x="{x + 60}" y="{by + 4}" width="{bw:.0f}" height="16" rx="8" fill="{GOLD}"/>')
        parts.append(
            f'<text x="{x + w + 12}" y="{by + 18}" fill="{SUB}" font-size="20">{vector[d]}</text>'
        )
    return "".join(parts)


def render_card(
    persona: dict,
    user_vec: dict,
    fit: int,
    match_items_list: list[dict],
    tip: str,
    copy_text: str,
    universe_zh: str,
    out_path: str | None = None,
) -> str:
    """渲染身份卡 SVG，返回文件路径。"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if not out_path:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(OUTPUT_DIR, f"mcparallel_{persona['id']}_{stamp}.svg")

    items_lines = []
    for i, it in enumerate(match_items_list):
        iy = 1150 + i * 54
        items_lines.append(
            f'<text x="90" y="{iy}" fill="{TEXT}" font-size="26">'
            f'<tspan fill="{GOLD}" font-size="22">{i + 1}.</tspan> '
            f'{_esc(it["name"])}'
            f'<tspan fill="{SUB}" font-size="22" dx="16">¥{it["price"]}</tspan></text>'
        )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#1b1b2a"/><stop offset="1" stop-color="{BG}"/>
    </linearGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <rect x="24" y="24" width="{W - 48}" height="{H - 48}" rx="28" fill="none" stroke="{RED}" stroke-width="4"/>

  <!-- 头部 -->
  <text x="70" y="86" fill="{GOLD}" font-size="30" font-weight="bold">🍔 麦门平行宇宙 McParallel</text>
  <text x="{W - 70}" y="86" fill="{SUB}" font-size="24" text-anchor="end">{_esc(universe_zh)}</text>
  <line x1="70" y1="110" x2="{W - 70}" y2="110" stroke="#3a3a4e" stroke-width="2"/>

  <!-- 人格名与契合度 -->
  <text x="70" y="208" fill="{TEXT}" font-size="64" font-weight="bold">{_esc(persona["name"])}</text>
  <text x="70" y="258" fill="{SUB}" font-size="28">「{_esc(persona["tagline"])}」</text>
  <rect x="{W - 320}" y="150" width="250" height="96" rx="20" fill="{RED}"/>
  <text x="{W - 195}" y="192" fill="#fff" font-size="26" text-anchor="middle">契合度</text>
  <text x="{W - 195}" y="230" fill="#fff" font-size="42" font-weight="bold" text-anchor="middle">{fit}%</text>

  <!-- 雷达图 -->
  {_radar_svg(600, 560, 210, user_vec, persona["vector"])}
  <text x="90" y="830" fill="{SUB}" font-size="20">— — 人格口味画像　● 你的口味向量</text>

  <!-- 五维条形 -->
  <text x="70" y="880" fill="{GOLD}" font-size="26" font-weight="bold">你的麦门口味五维</text>
  {_bars_svg(90, 900, 700, user_vec)}

  <!-- 适配套餐 -->
  <text x="70" y="1110" fill="{GOLD}" font-size="26" font-weight="bold">TA 会点什么（实时菜单适配）</text>
  {"".join(items_lines)}

  <!-- 省钱 tip -->
  <rect x="70" y="1280" width="{W - 140}" height="100" rx="16" fill="{PANEL}"/>
  <text x="94" y="1318" fill="{GOLD}" font-size="24" font-weight="bold">💡 专属省钱 tip</text>
  <text x="94" y="1352" fill="{TEXT}" font-size="24">{_esc(tip)}</text>

  <!-- 推荐文案 -->
  <rect x="70" y="1400" width="{W - 140}" height="130" rx="16" fill="{PANEL}"/>
  <text x="94" y="1438" fill="{GOLD}" font-size="24" font-weight="bold">✍️ 人格推荐语</text>
  <text x="94" y="1474" fill="{TEXT}" font-size="24">{_esc(copy_text[:64])}</text>
  <text x="94" y="1506" fill="{TEXT}" font-size="24">{_esc(copy_text[64:128])}</text>

  <!-- 页脚 -->
  <line x1="70" y1="1560" x2="{W - 70}" y2="1560" stroke="#3a3a4e" stroke-width="2"/>
  <text x="70" y="1596" fill="{SUB}" font-size="20">数据来源：麦当劳官方 MCP（实时菜单/营养/价格） · 菜品与价格以官方渠道实时为准</text>
  <text x="70" y="1628" fill="{SUB}" font-size="20">麦门平行宇宙 · 参赛作品（非官方产品） · 内容仅供娱乐，健康饮食请均衡搭配</text>
  <text x="{W - 70}" y="1628" fill="{SUB}" font-size="20" text-anchor="end">mcparallel · {_esc(persona["id"])}</text>
</svg>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return out_path
