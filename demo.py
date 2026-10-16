#!/usr/bin/env python3
"""麦门平行宇宙 · 30 秒离线 Demo —— 无需 Token，回放真实 MCP 录制数据。

python demo.py            # 离线（默认，零门槛）
python demo.py --online   # 在线真实调用（需要 .env 中的 MCD_MCP_TOKEN）
python demo.py --record   # 在线调用并刷新 fixtures 录制
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcparallel.card import render_card
from mcparallel.cli import Context
from mcparallel.draw import draw_summary, draw_three
from mcparallel.guide import budget_search, persona_tip
from mcparallel.llm_copy import generate_copy
from mcparallel.matching import match_items, match_personas, taste_vector
from mcparallel.menu import POOL_ZH
from mcparallel.personas import UNIVERSE_ZH
from mcparallel.quiz import load_quiz, quiz_summary, quiz_vector
from mcparallel.savings import savings_summary
from mcparallel.tag_matrix import fmt_vector


def pick(items, keyword):
    for it in items:
        if it["name"] == keyword:
            return it
    for it in items:
        if keyword in it["name"] and it["pool"] != "other":
            return it
    raise KeyError(f"菜单中找不到含「{keyword}」的单品")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    print("=" * 62)
    print("🍔 麦门平行宇宙 McParallel · Demo（数据：麦当劳官方 MCP 实时/录制）")
    print("=" * 62)

    # ① 统一数据底座
    print("\n① 统一数据底座")
    ctx = Context(offline=mode not in ("--online", "--record"))
    items, personas = ctx.items, ctx.personas
    pools: dict[str, list] = {}
    for it in items:
        pools.setdefault(it["pool"], []).append(it)
    for pool in ("staple", "snack", "drink", "combo", "other"):
        if pools.get(pool):
            print(f"   {POOL_ZH[pool]}池: {len(pools[pool])} 个单品")
    matched = sum(1 for it in items if it.get("nutrition"))
    print(f"   营养数据关联: {matched}/{len(items)} 个单品命中官方营养表")
    print(f"   人格原型库: {len(personas)} 个 / {len(UNIVERSE_ZH)} 大宇宙")

    # ② 板块一：三连抽 + 最优购买方案
    print("\n② 板块一 · 三连抽「今天吃什么」（人格加权 + 优惠引擎）")
    assassin = next(p for p in personas if p["name"] == "峡谷刺客型")
    result = draw_three(items, persona_vec=assassin["vector"], seed=7)
    print(draw_summary(result))
    print(f"   （已按「{assassin['name']}」的口味向量加权抽取）")
    print(savings_summary(ctx.engine.evaluate(list(result["picks"].values()))))

    # ③ 板块二：场景题鉴定（预设答案演示）
    print("\n③ 板块二 · 麦人格鉴定（游戏宇宙 · 预设答案 A,A,A 演示）")
    answers = ["A", "A", "A"]
    print(quiz_summary("game", load_quiz()["game"], answers))
    base = {d: sum(it["vector"][d] for it in items) / len(items) for d in items[0]["vector"]}
    vec = quiz_vector("game", answers, base)
    persona, fit = match_personas(vec, personas, items, top_n=1, universe="game")[0]
    print(f"\n   🎴 鉴定结果：{persona['name']}（契合度 {fit}%）「{persona['tagline']}」")
    print(f"   你的口味五维: {fmt_vector(vec)}")
    picks = match_items(vec, items, top_n=3)
    for it in picks:
        print(f"     → {it['name']:<14} ¥{it['price']}")
    copy = generate_copy(persona, picks)
    print(f"   ✍️ {copy['text']}（{copy['source']}）")

    # ④ 板块二：逆向鉴定（常点组合）
    print("\n④ 板块二 · 逆向鉴定：常点「巨无霸 + 麦乐鸡 + 可乐」")
    chosen = [pick(items, "巨无霸"), pick(items, "麦乐鸡"), pick(items, "可乐")]
    tv = taste_vector(chosen, items)
    print(f"   口味五维: {fmt_vector(tv)}")
    for p, f in match_personas(tv, personas, items, top_n=3):
        print(f"   → {f}% {p['name']:<14}「{p['tagline']}」")

    # ⑤ 板块三：高性价比指南
    print("\n⑤ 板块三 · 高性价比指南（预算定制示例）")
    plan = budget_search(items, 25)
    status = "达标" if plan["enough"] else "未达标"
    print(f"   预算 ¥25 吃饱方案（≥500 kcal）：{status}")
    for r in plan["picks"]:
        print(f"     → {r['name']:<14} ¥{r['price']:<6} {r['kcal']} kcal（{r['kcal_per_yuan']} kcal/元）")
    print(f"     合计：¥{plan['total_price']} / {plan['total_kcal']} kcal")
    print(f"   💡 人格专属 tip：{persona_tip(persona)}")
    print("   完整指南见 GUIDE.md（健身高碳/低碳日 · 减脂 500 大卡线 · 学生党 kcal/元排行）")

    # ⑥ 身份卡
    print("\n⑥ 麦门身份卡（SVG，GitHub 原生可渲染）")
    # 修复：改为固定路径覆盖写，并清理历史运行遗留的时间戳卡片（不再污染仓库）
    from mcparallel.card import OUTPUT_DIR
    import glob as _glob
    for stale in _glob.glob(os.path.join(OUTPUT_DIR, "mcparallel_*.svg")):
        os.remove(stale)
    card_path = render_card(
        persona, vec, fit, picks, persona_tip(persona), copy["text"], UNIVERSE_ZH["game"],
        out_path=os.path.join(OUTPUT_DIR, "demo-card.svg"),
    )
    print(f"   已生成：{card_path}")

    print("\n更多玩法：python -m mcparallel --help（quiz 交互鉴定 / draw / forward / reverse / guide / lottery）")
    print("=" * 62)


if __name__ == "__main__":
    main()
