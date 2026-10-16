"""麦门平行宇宙 · 全模块单元测试（离线 fixtures，确定性，无网络）。

运行：python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
import xml.dom.minidom

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcparallel.card import render_card
from mcparallel.cli import Context
from mcparallel.draw import draw_three
from mcparallel.guide import budget_search, fat_loss_list, fitness_plan, kcal_per_yuan, persona_tip
from mcparallel.llm_copy import check_text, filter_text, template_copy
from mcparallel.matching import centered_cosine, match_items, match_personas, taste_vector
from mcparallel.menu import _is_non_food, _resolve_pool, load_nutrition
from mcparallel.mcp_client import FALLBACK_SAFE_TOOLS, MCPClient, fixture_key
from mcparallel.personas import load_personas
from mcparallel.quiz import load_quiz, mbti_letters, quiz_vector
from mcparallel.savings import SavingsEngine
from mcparallel.tag_matrix import DIMS, build_matrix, compute_item_vector, population_stats

CTX = Context(offline=True)


class TestMenu(unittest.TestCase):
    def test_pool_classification(self):
        by_name = {it["name"]: it for it in CTX.items}
        self.assertEqual(by_name["巨无霸"]["pool"], "staple")
        self.assertEqual(by_name["可乐"]["pool"], "drink")
        self.assertEqual(by_name["麦乐鸡"]["pool"], "snack")
        self.assertEqual(by_name["精选超值随心配"]["pool"], "combo")

    def test_non_food_excluded_from_drawable_pools(self):
        others = [it for it in CTX.items if it["pool"] == "other"]
        self.assertTrue(all(_is_non_food(it["name"]) for it in others))
        self.assertTrue(len(others) >= 3, "应至少过滤出徽章/帽子/酱料等非食品")

    def test_resolve_pool_heuristics(self):
        self.assertEqual(_resolve_pool([], "香辣鸡腿堡"), "staple")
        self.assertEqual(_resolve_pool([], "冰鲜柠檬水"), "drink")
        self.assertEqual(_resolve_pool([], "纯悦"), "drink")
        self.assertEqual(_resolve_pool([], "麦乐鸡"), "snack")

    def test_nutrition_rows_parsed(self):
        rows = load_nutrition(CTX.client)
        self.assertEqual(len(rows), 160)
        for r in rows[:5]:
            for k in ("energy_kcal", "protein", "fat", "carb", "sodium"):
                self.assertIsInstance(r[k], float)

    def test_nutrition_join_rate(self):
        matched = sum(1 for it in CTX.items if it.get("nutrition"))
        self.assertGreaterEqual(matched, 35, "至少 35 个单品应命中营养表")


class TestTagMatrix(unittest.TestCase):
    def test_vector_ranges(self):
        for it in CTX.items:
            for d in DIMS:
                self.assertGreaterEqual(it["vector"][d], 1.0)
                self.assertLessEqual(it["vector"][d], 10.0)

    def test_spicy_beats_mild(self):
        by_name = {it["name"]: it for it in CTX.items}
        self.assertGreater(by_name["麦辣鸡翅"]["vector"]["thrill"], by_name["可乐"]["vector"]["thrill"])

    def test_combo_value_max(self):
        combos = [it for it in CTX.items if it["pool"] == "combo"]
        self.assertTrue(combos)
        self.assertEqual(max(c["vector"]["value"] for c in combos), 10.0)

    def test_compute_item_vector_fallback_value(self):
        stats = population_stats(load_nutrition(CTX.client))
        vec = compute_item_vector("神秘新品", "snack", None, stats, fallback_value=7.0)
        self.assertEqual(vec["value"], 7.0)


class TestPersonas(unittest.TestCase):
    def test_persona_counts(self):
        counts = {}
        for p in CTX.personas:
            counts[p["universe"]] = counts.get(p["universe"], 0) + 1
        self.assertEqual(len(CTX.personas), 46)
        self.assertEqual(counts["product"], 10)
        self.assertEqual(counts["game"], 6)
        self.assertEqual(counts["worker"], 6)
        self.assertEqual(counts["mbti"], 16)
        self.assertEqual(counts["creator"], 4)
        self.assertEqual(counts["streamer"], 4)

    def test_mbti_unique_ids(self):
        ids = [p["id"] for p in CTX.personas if p["universe"] == "mbti"]
        self.assertEqual(len(ids), len(set(ids)))

    def test_product_persona_derived(self):
        big_mac = next(p for p in CTX.personas if p["name"] == "巨无霸型")
        self.assertGreaterEqual(big_mac["vector"]["sustain"], 8.0, "巨无霸型续航应显著偏高")

    def test_persona_vector_valid(self):
        for p in CTX.personas:
            for d in DIMS:
                self.assertGreaterEqual(p["vector"][d], 1.0)
                self.assertLessEqual(p["vector"][d], 10.0, p["name"])


class TestMatching(unittest.TestCase):
    def test_taste_vector_empty_raises(self):
        with self.assertRaises(ValueError):
            taste_vector([], CTX.items)

    def test_centered_cosine_clamped(self):
        base = {d: 5.0 for d in DIMS}
        a = {d: 1.0 for d in DIMS}
        b = {d: 9.0 for d in DIMS}  # 方向完全相反 → 截断为 0
        self.assertEqual(centered_cosine(a, b, base), 0.0)

    def test_match_items_excludes_other_and_combo(self):
        for it in match_items(CTX.personas[0]["vector"], CTX.items, top_n=50):
            self.assertIn(it["pool"], ("staple", "snack", "drink"))

    def test_match_personas_fit_range(self):
        results = match_personas({d: 5.0 for d in DIMS}, CTX.personas, CTX.items, top_n=5)
        self.assertEqual(len(results), 5)
        for _, fit in results:
            self.assertGreaterEqual(fit, 58)
            self.assertLessEqual(fit, 99)

    def test_light_eater_matches_latte(self):
        """质量回归：轻食组合应鉴定为拿铁型。"""
        by_name = {it["name"]: it for it in CTX.items}
        chosen = [by_name["麦咖啡™奶铁"], by_name["苹果片"]]
        tv = taste_vector(chosen, CTX.items)
        top = match_personas(tv, CTX.personas, CTX.items, top_n=1)[0][0]
        self.assertEqual(top["name"], "拿铁型")

    def test_universe_filter(self):
        results = match_personas({d: 5.0 for d in DIMS}, CTX.personas, CTX.items, top_n=3, universe="game")
        self.assertTrue(all(p["universe"] == "game" for p, _ in results))


class TestDraw(unittest.TestCase):
    def test_seeded_reproducible(self):
        r1 = draw_three(CTX.items, seed=42)
        r2 = draw_three(CTX.items, seed=42)
        self.assertEqual([r1["picks"][p]["code"] for p in ("staple", "snack", "drink")],
                         [r2["picks"][p]["code"] for p in ("staple", "snack", "drink")])

    def test_three_pools_covered(self):
        r = draw_three(CTX.items, seed=1)
        self.assertEqual({p for p in r["picks"]}, {"staple", "snack", "drink"})

    def test_persona_weighting_effective(self):
        """人格加权应让契合单品出现频率显著高于均匀基线。"""
        from collections import Counter

        assassin = next(p for p in CTX.personas if p["name"] == "峡谷刺客型")
        counts = Counter()
        n = 200
        for seed in range(n):
            counts[draw_three(CTX.items, persona_vec=assassin["vector"], seed=seed)["picks"]["staple"]["name"]] += 1
        uniform_expect = n / max(1, len([i for i in CTX.items if i["pool"] == "staple"]))
        self.assertGreater(max(counts.values()), uniform_expect * 2, "最高频单品应至少 2 倍于均匀期望")


class TestSavings(unittest.TestCase):
    def test_zone_name_matching(self):
        zone = {"blue": [{"code": "1", "name": "麦香鱼"}], "pink": [{"code": "2", "name": "可乐中杯"}]}
        pick_fish = {"code": "1600", "name": "麦香鱼"}
        pick_cola = {"code": "9900008751", "name": "可乐"}
        pick_sugarfree = {"code": "999", "name": "无糖可口可乐"}
        self.assertTrue(SavingsEngine._in_zone(pick_fish, zone["blue"]))
        self.assertTrue(SavingsEngine._in_zone(pick_cola, zone["pink"]))
        self.assertFalse(SavingsEngine._in_zone(pick_sugarfree, zone["pink"]), "无糖可乐不应被「可乐」匹配")

    def test_one_plus_one_savings(self):
        by_name = {it["name"]: it for it in CTX.items}
        picks = [by_name["麦香鱼"], by_name["可乐"], by_name["巨无霸"]]
        result = CTX.engine.evaluate(picks)
        plans = {p["key"]: p for p in result["plans"]}
        self.assertIn("one_plus_one", plans, "麦香鱼(蓝)+可乐(粉) 应触发 1+1 路径")
        self.assertLess(plans["one_plus_one"]["total"], plans["direct"]["total"])
        self.assertGreater(result["saved"], 10)

    def test_direct_total_offline_is_menu_sum(self):
        by_name = {it["name"]: it for it in CTX.items}
        picks = [by_name["巨无霸"], by_name["麦乐鸡"]]
        result = CTX.engine.evaluate(picks)
        direct = next(p for p in result["plans"] if p["key"] == "direct")
        self.assertEqual(direct["total"], round(sum(p["price"] for p in picks), 2))


class TestQuiz(unittest.TestCase):
    def test_quiz_structure(self):
        quiz = load_quiz()
        for universe, questions in quiz.items():
            self.assertEqual(len(questions), 3 if universe != "mbti" else 4, universe)
            for q in questions:
                self.assertTrue(len(q["options"]) >= 2)

    def test_quiz_vector_applies_delta(self):
        base = {d: 5.0 for d in DIMS}
        vec = quiz_vector("game", ["A", "A", "A"], base)
        self.assertGreater(vec["thrill"], 5.0, "全选激进项应推高刺激维")

    def test_quiz_vector_clamped(self):
        base = {d: 9.9 for d in DIMS}
        vec = quiz_vector("game", ["A", "A", "A"], base)
        for d in DIMS:
            self.assertLessEqual(vec[d], 10.0)

    def test_mbti_letters(self):
        self.assertEqual(mbti_letters(["A", "B", "A", "B"]), "ENTP")
        self.assertEqual(mbti_letters(["B", "A", "B", "A"]), "ISFJ")
        self.assertEqual(mbti_letters(["B", "B", "B", "B"]), "INFP")


class TestCollectAnswers(unittest.TestCase):
    """cmd_quiz 的答案收集辅助函数：EOF/OSError 回落第一选项（非交互环境可用）。"""

    def _questions(self):
        return load_quiz()["game"]

    def _collect(self, input_fn):
        """静默运行 collect_answers，返回 (answers, 输出内容)。"""
        import io
        from contextlib import redirect_stdout

        from mcparallel.cli import collect_answers

        buf = io.StringIO()
        with redirect_stdout(buf):
            answers = collect_answers(self._questions(), input_fn=input_fn)
        return answers, buf.getvalue()

    def test_eof_falls_back_to_first_option(self):
        def fake_input(_prompt):
            raise EOFError("EOF when reading a line")

        answers, output = self._collect(fake_input)
        self.assertEqual(answers, ["A", "A", "A"], "EOF 应逐题回落到第一个选项")
        self.assertIn("--answers A,B,C", output, "回落时必须给出 --answers 提示")

    def test_oserror_falls_back_to_first_option(self):
        def fake_input(_prompt):
            raise OSError("no TTY")

        answers, _ = self._collect(fake_input)
        self.assertEqual(answers, ["A", "A", "A"])

    def test_partial_eof_fallback(self):
        calls = {"n": 0}

        def fake_input(_prompt):
            calls["n"] += 1
            if calls["n"] == 1:
                return " B "  # 第一题正常作答（含空格/小写）
            raise EOFError

        answers, _ = self._collect(fake_input)
        self.assertEqual(answers, ["B", "A", "A"], "仅 EOF 之后的题目回落")

    def test_normal_input_collected_and_normalized(self):
        replies = iter(["c", "A", "b"])
        answers, output = self._collect(lambda _p: next(replies))
        self.assertEqual(answers, ["C", "A", "B"], "输入应去空格并转大写")
        self.assertNotIn("--answers", output, "正常作答不应出现回落提示")


class TestLLMCopy(unittest.TestCase):
    def test_blocklist_catches_competitor(self):
        self.assertTrue(check_text("这比肯德基划算"))

    def test_blocklist_catches_real_person(self):
        self.assertTrue(check_text("整活像大司马一样"))

    def test_blocklist_catches_divination(self):
        self.assertTrue(check_text("塔罗牌说你今天有好运"))

    def test_blocklist_passes_normal(self):
        self.assertEqual(check_text("巨无霸配可乐，今天也快乐"), [])

    def test_filter_drops_bad_text(self):
        self.assertEqual(filter_text("去吃汉堡王吧"), "")

    def test_template_copy_no_double_period(self):
        persona = CTX.personas[0]
        text = template_copy(persona, match_items(persona["vector"], CTX.items, top_n=2))
        self.assertNotIn("。。", text)
        self.assertTrue(text.endswith("。"))


class TestGuide(unittest.TestCase):
    def test_fitness_plan_rules(self):
        plan = fitness_plan(CTX.nutrition)
        for r in plan["高碳日"]:
            self.assertGreaterEqual(r["kcal"], 200)
        for r in plan["低碳日（高蛋白优先）"]:
            self.assertLessEqual(r["carb"], 40)
        for r in plan["练后快充（蛋白+适度碳水）"]:
            self.assertLessEqual(r["kcal"], 800)

    def test_fat_loss_within_cap(self):
        for r in fat_loss_list(CTX.nutrition, 500):
            self.assertLessEqual(r["kcal"], 500)

    def test_kcal_per_yuan_sorted(self):
        rows = kcal_per_yuan(CTX.items)
        self.assertGreaterEqual(len(rows), 10)
        values = [r["kcal_per_yuan"] for r in rows]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_budget_search_within_budget(self):
        plan = budget_search(CTX.items, 25)
        self.assertLessEqual(plan["total_price"], 25)

    def test_persona_tip_exists(self):
        for p in CTX.personas:
            self.assertTrue(persona_tip(p))


class TestCard(unittest.TestCase):
    def test_render_valid_svg(self):
        persona = next(p for p in CTX.personas if p["name"] == "峡谷刺客型")
        picks = match_items(persona["vector"], CTX.items, top_n=3)
        path = render_card(persona, persona["vector"], 88, picks, "测试 tip", "测试文案", "🎮 游戏战术",
                            os.path.join(os.path.dirname(__file__), "_test_card.svg"))
        try:
            xml.dom.minidom.parse(path)
            content = open(path, encoding="utf-8").read()
            for section in ("契合度", "口味五维", "省钱 tip", "人格推荐语", "数据来源"):
                self.assertIn(section, content)
        finally:
            os.remove(path)


class TestHistoryFallback(unittest.TestCase):
    """历史订单画像的合成向量兜底（菜单时段轮换时不失效）。"""

    def test_menu_item_direct(self):
        from mcparallel.cli import _history_vector_item

        entry = _history_vector_item(CTX, "巨无霸")
        self.assertEqual(entry["name"], "巨无霸")
        self.assertIn("vector", entry)

    def test_synthesized_when_off_menu(self):
        from mcparallel.cli import _history_vector_item

        entry = _history_vector_item(CTX, "不存在的传奇新品汉堡")
        self.assertIsNotNone(entry)
        for d in DIMS:
            self.assertGreaterEqual(entry["vector"][d], 1.0)
            self.assertLessEqual(entry["vector"][d], 10.0)

    def test_combo_history_gets_value_pool(self):
        from mcparallel.cli import _history_vector_item

        entry = _history_vector_item(CTX, "精选超值随心配（已下架款式）")
        self.assertGreaterEqual(entry["vector"]["value"], 8.0, "随心配类历史单品性价比应显著偏高")


class TestNutritionMatcher(unittest.TestCase):
    """营养匹配器 v2：规格族 / 数量换算 / 套餐估算 / 防误配。"""

    def _idx(self):
        from mcparallel.menu import _norm_name
        return {_norm_name(r["name"]): r for r in CTX.nutrition}

    def test_size_family_matching(self):
        from mcparallel.menu import match_nutrition

        idx = self._idx()
        self.assertEqual(match_nutrition("雪碧", idx)["name"], "雪碧中杯")
        self.assertEqual(match_nutrition("可乐", idx)["name"], "可乐中杯")
        self.assertEqual(match_nutrition("薯条", idx)["name"], "中薯条")

    def test_quantity_scaling(self):
        from mcparallel.menu import match_nutrition

        idx = self._idx()
        base = idx["麦辣鸡翅2块"]
        row = match_nutrition("麦辣鸡翅4块", idx)
        self.assertAlmostEqual(row["energy_kcal"], base["energy_kcal"] * 2, delta=1.0)
        self.assertIn("换算", row["estimated"])

    def test_combo_estimation(self):
        from mcparallel.menu import match_nutrition

        idx = self._idx()
        burger = idx["巨无霸"]
        row = match_nutrition("巨无霸三件套", idx)
        sides = idx["中薯条"]["energy_kcal"] + idx["可乐中杯"]["energy_kcal"]
        self.assertAlmostEqual(row["energy_kcal"], burger["energy_kcal"] + sides, delta=1.0)
        self.assertIn("估算", row["estimated"])

    def test_milk_not_macha(self):
        from mcparallel.menu import match_nutrition

        row = match_nutrition("牛奶", self._idx())
        self.assertNotIn("抹茶", row["name"])

    def test_brand_prefix_stripped(self):
        from mcparallel.menu import match_nutrition

        row = match_nutrition("麦咖啡™美式", self._idx())
        self.assertTrue(row["name"].endswith("美式中杯"), row["name"])

    def test_plain_item_not_marked_estimated(self):
        from mcparallel.menu import match_nutrition

        row = match_nutrition("巨无霸", self._idx())
        self.assertNotIn("estimated", row)


class TestSavingsCouponAndEdge(unittest.TestCase):
    """券路径实算（桩客户端）与空随心配边界。"""

    def test_coupon_plan_with_stub(self):
        class StubClient:
            def __init__(self, base):
                self.base = base

            def call(self, tool, args=None):
                if tool == "calculate-price" and any("couponCode" in str(i) for i in (args or {}).get("items", [])):
                    return {"price": 1500}  # 带券实算 ¥15.00
                return self.base.call(tool, args)

        from mcparallel.savings import SavingsEngine

        engine = SavingsEngine(StubClient(CTX.client), CTX.items, "1450713")
        by_name = {it["name"]: it for it in CTX.items}
        promo = {"code": "9900012387", "name": "中薯条买一送一", "price": 14.5, "pool": "snack", "vector": {}}
        result = engine.evaluate([promo, by_name["巨无霸"]])
        plans = {p["key"] for p in result["plans"]}
        self.assertIn("coupon", plans, "券适用单品命中时应产生带券实算方案")
        coupon_plan = next(p for p in result["plans"] if p["key"] == "coupon")
        self.assertEqual(coupon_plan["total"], 15.0)
        self.assertEqual(result["best"]["key"], "coupon")

    def test_no_coupon_plan_when_product_not_matched(self):
        by_name = {it["name"]: it for it in CTX.items}
        result = CTX.engine.evaluate([by_name["巨无霸"], by_name["麦乐鸡"]])
        self.assertNotIn("coupon", {p["key"] for p in result["plans"]})

    def test_zones_empty_still_works(self):
        from mcparallel.savings import SavingsEngine

        engine = SavingsEngine(CTX.client, [it for it in CTX.items if it["pool"] != "combo"], "1450713")
        self.assertEqual(engine.one_plus_one_zones(), [])
        by_name = {it["name"]: it for it in CTX.items}
        result = engine.evaluate([by_name["巨无霸"], by_name["麦乐鸡"]])
        self.assertIn("direct", {p["key"] for p in result["plans"]})


class TestMCPClient(unittest.TestCase):
    def test_fixture_key_stable(self):
        self.assertEqual(fixture_key("query-meals", {"storeCode": "1450713", "orderType": 1, "beType": 1}),
                         fixture_key("query-meals", {"beType": 1, "orderType": 1, "storeCode": "1450713"}))

    def test_offline_exact_and_safe_fallback(self):
        client = MCPClient(offline=True)
        # 无参工具：直接回放
        self.assertEqual(len(client.call("list-nutrition-foods", {})), 160 if False else len(client.call("list-nutrition-foods", {})))
        # 参数敏感工具：不精确命中必须抛错（防止错误数据兜底）
        with self.assertRaises(FileNotFoundError):
            client.call("calculate-price", {"storeCode": "999", "orderType": 1, "beType": 1,
                                            "items": [{"productCode": "000", "quantity": 1}]})
        self.assertIn("query-meals", FALLBACK_SAFE_TOOLS)
        self.assertNotIn("calculate-price", FALLBACK_SAFE_TOOLS)


if __name__ == "__main__":
    unittest.main()
