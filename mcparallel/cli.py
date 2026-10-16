"""统一 CLI：三合一全流程入口。

    python -m mcparallel draw [--persona 峡谷刺客型] [--seed 7]     # 板块一：三连抽+优惠引擎
    python -m mcparallel quiz --universe game                       # 板块二：交互式场景题鉴定
    python -m mcparallel quiz --universe game --answers A,B,C       # 非交互
    python -m mcparallel forward --persona 峡谷刺客型               # 板块二：TA会吃什么
    python -m mcparallel reverse --items 巨无霸,麦乐鸡,可乐         # 板块二：常点组合鉴定
    python -m mcparallel guide [--budget 25] [--goal fitness|fatloss]  # 板块三
    python -m mcparallel card --universe game --answers A,B,C       # 生成 SVG 身份卡
    python -m mcparallel lottery                                    # 真抽卡模式（奖品池展示）
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .card import render_card
from .draw import draw_summary, draw_three
from .guide import budget_search, fat_loss_list, fitness_plan, kcal_per_yuan, persona_tip
from .llm_copy import generate_copy
from .matching import baseline_from_items, match_items, match_personas, taste_vector
from .menu import DEFAULT_STORE, attach_nutrition, load_menu, load_nutrition
from .mcp_client import MCPClient
from .personas import UNIVERSE_ZH, load_personas
from .quiz import load_quiz, mbti_letters, quiz_summary, quiz_vector
from .savings import SavingsEngine, savings_summary
from .tag_matrix import DIMS, build_matrix, fmt_vector


class Context:
    """一次性加载全量数据（菜单 × 营养 × 人格 × 优惠引擎）。"""

    def __init__(self, offline: bool = True):
        self.client = MCPClient(offline=offline)
        self.nutrition = load_nutrition(self.client)
        self.items = build_matrix(attach_nutrition(load_menu(self.client), self.nutrition), self.nutrition)
        self.personas = load_personas(self.items, self.nutrition)
        self.engine = SavingsEngine(self.client, self.items, DEFAULT_STORE)
        self.baseline = baseline_from_items(self.items)

    def persona_by_name(self, name: str) -> dict:
        for p in self.personas:
            if p["name"] == name or name in p["name"]:
                return p
        known = "、".join(p["name"] for p in self.personas)
        raise SystemExit(f"找不到人格「{name}」。可选：{known}")

    def pick_item(self, name: str) -> dict:
        for it in self.items:
            if it["name"] == name:
                return it
        for it in self.items:
            if name in it["name"] and it["pool"] != "other":
                return it
        raise SystemExit(f"菜单中找不到「{name}」")


# ---------- 子命令 ----------

def cmd_draw(ctx: Context, args):
    persona = ctx.persona_by_name(args.persona) if args.persona else None
    result = draw_three(ctx.items, persona_vec=persona["vector"] if persona else None, seed=args.seed)
    print(draw_summary(result))
    if persona:
        print(f"（已按 {persona['name']} 的口味向量加权抽取）")
    picks = list(result["picks"].values())
    print()
    print(savings_summary(ctx.engine.evaluate(picks)))


def collect_answers(questions: list[dict], input_fn=input) -> list[str]:
    """逐题收集答案；input_fn 可注入以便测试（禁止用真实 input() 做单测）。

    非交互环境（EOF/管道/无 TTY）下 input 抛 EOFError/OSError 时，
    回落到该题第一个选项——与 quiz.py 的 mbti_letters 对无效答案的
    兜底策略保持一致，保证 CI/智能体场景可用。
    """
    answers = []
    fallback = False
    for i, q in enumerate(questions):
        print(f"\nQ{i + 1}. {q['text']}")
        for opt in q["options"]:
            print(f"   {opt['label']}. {opt['text']}")
        try:
            answers.append(input_fn("你的选择：").strip().upper() or "A")
        except (EOFError, OSError):
            fallback = True
            answers.append(q["options"][0]["label"])
    if fallback:
        print("\n⚠️ 检测到非交互环境（EOF），已按每题第一个选项作答。"
              "非交互环境建议使用 --answers A,B,C")
    return answers


def cmd_quiz(ctx: Context, args):
    universe = args.universe
    if universe not in UNIVERSE_ZH:
        raise SystemExit(f"宇宙可选：{'、'.join(UNIVERSE_ZH.values())}")
    questions = load_quiz()[universe]
    answers = [a.strip().upper() for a in args.answers.split(",")] if args.answers else None
    if answers is None:
        print(f"=== {UNIVERSE_ZH[universe]} · 人格鉴定 ===")
        answers = collect_answers(questions)

    if universe == "mbti":
        code = mbti_letters(answers)
        persona = next(p for p in ctx.personas if p["id"] == f"mbti-{code}")
        base = {d: 5.0 for d in persona["vector"]}
        vec = persona["vector"]
        fit = 99
        print(f"\n你的麦门16型：{code}")
    else:
        base = {d: sum(it["vector"][d] for it in ctx.items) / len(ctx.items) for d in ctx.items[0]["vector"]}
        vec = quiz_vector(universe, answers, base)
        results = match_personas(vec, ctx.personas, ctx.items, top_n=1, universe=universe)
        if not results:
            raise SystemExit("该宇宙下没有可匹配的人格")
        persona, fit = results[0]

    print(quiz_summary(universe, questions, answers))
    print(f"\n🎴 鉴定结果：{persona['name']}（契合度 {fit}%）")
    print(f"   「{persona['tagline']}」")
    print(f"   你的口味五维：{fmt_vector(vec)}")
    print(f"   TA 会点什么：")
    for it in match_items(vec, ctx.items, top_n=3):
        print(f"     → {it['name']} ¥{it['price']}")
    tip = persona_tip(persona)
    copy = generate_copy(persona, match_items(vec, ctx.items, top_n=3))
    print(f"   💡 专属省钱 tip：{tip}")
    print(f"   ✍️ {copy['text']}（{copy['source']}）")


def cmd_forward(ctx: Context, args):
    persona = ctx.persona_by_name(args.persona)
    print(f"{persona['name']}「{persona['tagline']}」")
    print(f"口味画像：{fmt_vector(persona['vector'])}")
    picks = match_items(persona["vector"], ctx.items, top_n=3)
    for it in picks:
        print(f"→ {it['name']:<14} ¥{it['price']:<6} {fmt_vector(it['vector'])}")
    copy = generate_copy(persona, picks)
    print(f"\n✍️ {copy['text']}（{copy['source']}）")
    print()
    print(savings_summary(ctx.engine.evaluate(picks)))


def cmd_reverse(ctx: Context, args):
    names = [n.strip() for n in args.items.split(",") if n.strip()]
    chosen = []
    for n in names:
        entry = _history_vector_item(ctx, n)  # 当前菜单优先，时段轮换时营养表兜底
        if entry:
            chosen.append(entry)
    if not chosen:
        raise SystemExit("输入的单品无法解析（菜单与营养表均未命中）")
    vec = taste_vector(chosen, ctx.items)
    print(f"常点组合：{'、'.join(it['name'] for it in chosen)}")
    print(f"你的口味五维：{fmt_vector(vec)}")
    for p, fit in match_personas(vec, ctx.personas, ctx.items, top_n=3):
        print(f"→ {fit}% {p['name']:<14}「{p['tagline']}」")
    top = match_personas(vec, ctx.personas, ctx.items, top_n=1)[0][0]
    print(f"\n💡 专属省钱 tip：{persona_tip(top)}")


def cmd_guide(ctx: Context, args):
    if args.budget:
        result = budget_search(ctx.items, args.budget)
        status = "达标" if result["enough"] else "未达标（建议提高预算或凑随心配）"
        print(f"预算 ¥{args.budget} 吃饱方案（目标 ≥500 kcal）：{status}")
        for r in result["picks"]:
            print(f"  → {r['name']:<12} ¥{r['price']:<6} {r['kcal']} kcal（{r['kcal_per_yuan']} kcal/元）")
        print(f"  合计：¥{result['total_price']} / {result['total_kcal']} kcal")
        return
    if args.goal == "fitness":
        plan = fitness_plan(ctx.nutrition)
        for section in ("高碳日", "低碳日（高蛋白优先）", "练后快充（蛋白+适度碳水）"):
            print(f"\n🏋️ {section}")
            for r in plan[section][:5]:
                print(f"  → {r['name']:<12} {r['kcal']} kcal  碳水{r['carb']}g 蛋白{r['protein']}g")
    elif args.goal == "fatloss":
        print("🥗 500 大卡以内（蛋白质密度优先）")
        for r in fat_loss_list(ctx.nutrition)[:10]:
            print(f"  → {r['name']:<12} {r['kcal']} kcal  蛋白{r['protein']}g")
    else:
        print("🍕 kcal/元 排行（学生党效率榜）")
        for r in kcal_per_yuan(ctx.items)[:10]:
            print(f"  → {r['name']:<12} ¥{r['price']:<6} {r['kcal_per_yuan']} kcal/元")
        print("\n完整指南见 GUIDE.md；交互定制示例：python -m mcparallel guide --budget 25")


def cmd_card(ctx: Context, args):
    universe = args.universe or "game"
    questions = load_quiz().get(universe)
    if not questions:
        raise SystemExit(f"宇宙可选：{'、'.join(UNIVERSE_ZH)}")
    answers = [a.strip().upper() for a in args.answers.split(",")] if args.answers else None
    if answers is None:
        # 非交互生成卡时用每题第一个选项（确定性示例卡）
        answers = [q["options"][0]["label"] for q in questions]
    if universe == "mbti":
        code = mbti_letters(answers)
        persona = next(p for p in ctx.personas if p["id"] == f"mbti-{code}")
        vec = persona["vector"]
        fit = 99
    else:
        base = {d: sum(it["vector"][d] for it in ctx.items) / len(ctx.items) for d in ctx.items[0]["vector"]}
        vec = quiz_vector(universe, answers, base)
        persona, fit = match_personas(vec, ctx.personas, ctx.items, top_n=1, universe=universe)[0]
    picks = match_items(vec, ctx.items, top_n=3)
    copy = generate_copy(persona, picks)
    path = render_card(
        persona, vec, fit, picks, persona_tip(persona), copy["text"], UNIVERSE_ZH[universe], args.out
    )
    print(f"身份卡已生成：{path}")
    print(f"人格：{persona['name']}（{fit}%）  推荐语来源：{copy['source']}")


def _history_vector_item(ctx: Context, name: str) -> dict | None:
    """把历史订单单品转成可计算的向量条目。

    优先匹配当前菜单；菜单按时段轮换（早餐档没有随心配/薯条），
    匹配不到时退回营养表 + 池基准合成向量。
    """
    try:
        return ctx.pick_item(name)
    except SystemExit:
        pass
    from .menu import match_nutrition, _norm_name
    from .tag_matrix import compute_item_vector, guess_pool, population_stats

    idx = {_norm_name(r["name"]): r for r in ctx.nutrition}
    row = match_nutrition(name, idx)
    pool = "combo" if "随心配" in name else guess_pool(name)
    vec = compute_item_vector(name, pool, row, population_stats(ctx.nutrition))
    return {"name": name, "vector": vec}


def cmd_history(ctx: Context, args):
    """order-list 常点历史辅助画像（仅在线；只读，展示后即弃，不落盘）。"""
    if ctx.client.offline:
        raise SystemExit("常点历史画像需要在线模式（含个人订单数据，离线 fixtures 不收录）")
    try:
        orders = ctx.client.call("order-list", {})
    except (RuntimeError, FileNotFoundError) as e:
        raise SystemExit(f"无法读取历史订单：{e}")
    counter: dict[str, int] = {}
    for order in (orders or {}).get("list", []):
        for prod in order.get("orderProductList", []):
            name = prod.get("productName", "")
            if name:
                counter[name] = counter.get(name, 0) + int(prod.get("quantity", 1))
    if not counter:
        raise SystemExit("历史订单为空，试试 reverse --items 直接输入常点组合")
    top = sorted(counter.items(), key=lambda kv: -kv[1])[:8]
    print("📋 你的常点单品（仅本次展示，不存储）：")
    for name, qty in top:
        print(f"   {name} ×{qty}")

    # 历史单品合成向量（当前菜单优先，营养表兜底），并与菜单条目统一做归一化基线
    synth = []
    for name, _ in top:
        entry = _history_vector_item(ctx, name)
        if entry:
            synth.append(entry)
    if not synth:
        raise SystemExit("常点单品无法解析，试试 reverse --items")
    vec = {
        d: round(min(10.0, max(1.0, 0.6 * max(e["vector"][d] for e in synth)
                               + 0.4 * sum(e["vector"][d] for e in synth) / len(synth))), 1)
        for d in DIMS
    }
    print(f"\n你的口味五维：{fmt_vector(vec)}（全菜单基线：{fmt_vector({k: round(v, 1) for k, v in ctx.baseline.items()})}）")
    # 匹配人格：把合成向量与菜单条目并入同一比较空间
    merged = ctx.items + [{"name": e["name"], "vector": e["vector"], "pool": "snack"} for e in synth]
    for p, fit in match_personas(vec, ctx.personas, merged, top_n=3):
        print(f"→ {fit}% {p['name']:<14}「{p['tagline']}」")


def cmd_lottery(ctx: Context, args):
    try:
        info = ctx.client.call("query-lottery-info", {})
    except (RuntimeError, FileNotFoundError) as e:
        raise SystemExit(f"无法获取抽奖信息：{e}")
    data = info if isinstance(info, dict) else {}
    print(f"🎁 {data.get('activityName', '麦麦积分抽奖')}（{data.get('activityStatusText', '')}）")
    print(f"   消耗：{data.get('drawPoint', '?')} 积分/次   可用积分：{data.get('availablePoint', '?')}")
    decision = (data.get("drawDecision") or {}).get("nextConsumption") or {}
    if decision.get("text"):
        print(f"   {decision['text']}")
    prizes = data.get("prizes") or []
    if prizes:
        print("   奖品池：")
        for pz in prizes[:8]:
            print(f"     · {pz.get('name', '')}（{pz.get('typeText', '')}）")
    print("\n⚠️ 抽奖将真实消耗积分。执行抽奖需在确认对话中明确回复「确认抽奖」，")
    print("   本 CLI 仅展示奖品池与消耗，不自动执行 draw-lottery。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mcparallel", description="麦门平行宇宙 McParallel · 三合一 AI 点餐 Skill")
    parser.add_argument("--online", action="store_true", help="在线模式（默认离线 fixtures）")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("draw", help="三连抽 + 最优购买方案")
    p.add_argument("--persona", help="人格名（加权抽取）")
    p.add_argument("--seed", type=int, help="随机种子（结果可复现）")
    p.set_defaults(func=cmd_draw)

    p = sub.add_parser("quiz", help="场景题人格鉴定")
    p.add_argument("--universe", default="game", choices=list(UNIVERSE_ZH), help="宇宙")
    p.add_argument("--answers", help="非交互答案，如 A,B,C")
    p.set_defaults(func=cmd_quiz)

    p = sub.add_parser("forward", help="正向：TA 会吃什么")
    p.add_argument("--persona", required=True, help="人格名")
    p.set_defaults(func=cmd_forward)

    p = sub.add_parser("reverse", help="逆向：常点组合鉴定")
    p.add_argument("--items", required=True, help="逗号分隔的常点单品名")
    p.set_defaults(func=cmd_reverse)

    p = sub.add_parser("history", help="常点历史画像（在线，只读不落盘，需本人 Token）")
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("guide", help="高性价比指南")
    p.add_argument("--budget", type=float, help="预算（元）")
    p.add_argument("--goal", choices=["fitness", "fatloss"], help="人群目标")
    p.set_defaults(func=cmd_guide)

    p = sub.add_parser("card", help="生成 SVG 身份卡")
    p.add_argument("--universe", choices=list(UNIVERSE_ZH), help="宇宙（默认 game）")
    p.add_argument("--answers", help="非交互答案，如 A,B,C")
    p.add_argument("--out", help="输出路径（默认 output/cards/）")
    p.set_defaults(func=cmd_card)

    p = sub.add_parser("lottery", help="积分抽奖奖品池展示（确认制，不自动抽奖）")
    p.set_defaults(func=cmd_lottery)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    ctx = Context(offline=not args.online)
    args.func(ctx, args)


if __name__ == "__main__":
    main()
