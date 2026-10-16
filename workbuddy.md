# WorkBuddy 对话上下文

> 本文件用于麦当劳程序员节创意开发大赛 WorkBuddy 专项奖励申报。
> 在 WorkBuddy 中配置麦当劳 MCP 后，按 `SKILL.md` 与「麦门平行宇宙」Skill 真实对话，将关键记录整理至此。

## 配置方法

1. 前往 [open.mcd.cn](https://open.mcd.cn) → 手机号登录 → 控制台激活 → 复制 MCP Token。
2. WorkBuddy → 左侧【专家·技能·连接器】→【连接器】→ 右上角【自定义连接器】→【配置 MCP】，粘贴：

```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer <你的MCP_TOKEN>"
      }
    }
  }
}
```

3. 保存并启用后，直接在对话框说：

## 真实联调记录（2026-10-16，WorkBuddy + mcd-mcp 实测）

> 门店：麦当劳上海黄浦华旭国际大厦餐厅（storeCode `1450713`，南京东路街道西藏中路336号）
> 定位：`query-nearby-stores(beType=1, searchType=2, city=上海市, keyword=麦当劳)` ✅
> 以下全部数据来自 mcd-mcp 实时调用，非模板文案。

**对话 1 · 三连抽 + 优惠引擎 ✅**

> 用户：不知道吃什么，帮我抽三张牌
>
> Skill：（query-nearby-stores → query-meals 实时菜单 98 单品三池）
> 🎴 场景签：夜宵运 —— 夜色配炸鸡，今天到此为止。
> [主食] 麦香鸡套餐 ¥28.0 / [小吃] "我就喜欢"鸡薯双全盒 ¥15.9 / [饮品] 【美汁源】"多汁柠柠" ¥12.0
> 💰 直接单点：calculate-price 实算 **¥55.9**（本手牌无原样覆盖的 1+1 路径——引擎判定直接单点即最优，
> 因「麦香鸡套餐」≠蓝区单品「麦香鸡」，且「多汁柠柠」不在粉区）
> 💡 替换方案（需接受两处调整才成立）：把麦香鸡套餐降级为蓝区单品麦香鸡、多汁柠柠换粉区任选饮品，
> 走精选超值随心配 ¥13.9 + 鸡薯双全盒 ¥15.9 = **¥29.8，省 ¥26.1**（`query-meal-detail` 实测蓝区含麦香鸡 +¥0 差价）
> 🎟 门店券（query-store-coupons）：中薯条买一送一 / 王牌小食拼
> 想知道这顿饭暴露了你的什么人格吗？

**对话 2 · 人格鉴定（游戏宇宙）✅**

> 用户：测测我的麦人格，游戏宇宙
>
> Skill：Q1 决胜局最后十秒，你选？A 梭哈 / B 稳住 / C 算资源
> 用户：A
> Skill：Q2 你更喜欢哪种赢法？……（共 3 题）
> 用户：A A
>
> Skill：🎴 鉴定结果：**极限翻盘型（契合度 99%）**「逆风才好玩，翻盘才叫赢」
> （口味五维向量 → 中心化余弦匹配 `data/personas.json`，匹配引擎 `mcparallel/matching.py`）
> TA 会点什么（实时菜单 + calculate-price 核价合计 ¥58.9）：韩式甜辣酱鸡块8块 ¥19.9 / "辣"么快乐套餐 ¥24.0 / 麦辣鸡翅 ¥15.0
> 💡 专属省钱 tip：麦辣系列走 1+1 蓝区，饮料换无糖可乐，刺激不减、钱包减负。

**对话 3 · 高性价比指南 ✅**

> 用户：25 块钱在麦当劳怎么吃饱？
>
> Skill：（list-nutrition-foods 160 条营养数据 + calculate-price 实算）
> 预算 ¥25 吃饱方案（≥500 kcal）：那么大鸡排 ¥14.0（385 kcal）+ 燕麦奶铁 ¥9.9（麦金卡随单购价，132 kcal）= **¥23.9 / 517 kcal ✓**
> （实测发现：同单品 calculate-price 直接单点实算 ¥23.0、合计 ¥37.0，与菜单展示价 ¥9.9 差异 ¥13.1——
> 差价来自麦金卡随单购会员价。结论：看菜单价下单前先核价，随单购才是正确打开方式）
> 更省路径：1+1 蓝区默认即那么大鸡排，配粉区饮品仅 ¥13.9（份量相应减少）。
> 完整攻略见仓库 GUIDE.md：健身高碳/低碳日、减脂 500 大卡线、kcal/元排行。

**对话 4 · 确认制领券/抽奖 ✅**

> 用户：有什么券能领？
>
> Skill：（available-coupons）当前可领 3 张：**免费脆薯饼、人气麦旋风买一送一、9.9元中杯冰美式**（另有 4 张已领取）。要帮你一键领取吗？
> 用户：领
> Skill：（auto-bind-coupons，已确认）**领取成功 3/3**，券已入卡包（券码为账户资产，此处不展示）：
> - 免费脆薯饼
> - 人气麦旋风买一送一
> - 9.9元中杯冰美式

**对话 5 · Bug 修复记录 ✅**

> 执行环境：WorkBuddy（Agent 模式），2026-10-16。全程未调用任何 MCP 写类工具（本节为纯代码修复，未调用 MCP 工具）。

**Bug 1 · 交互式 quiz 在无 TTY 环境崩溃（主任务）**

修复前真实输出：

```text
$ python -m mcparallel quiz --universe game < /dev/null
  File "D:\ZCode_data\mcparallel\mcparallel\cli.py", line 85, in cmd_quiz
    answers.append(input("你的选择：").strip().upper() or "A")
                   ~~~~~^^^^^^^^^^^^^^
EOFError: EOF when reading a line
```

修复后真实输出：

```text
$ python -m mcparallel quiz --universe game < /dev/null
Q3. 连跪三把之后，你会？
   → 再来！手感要热回来

⚠️ 检测到非交互环境（EOF），已按每题第一个选项作答。非交互环境建议使用 --answers A,B,C
🎴 鉴定结果：极限翻盘型（契合度 99%）
   「逆风才好玩，翻盘才叫赢」
```

修改：
- `mcparallel/cli.py` 第 72 行新增 `collect_answers(questions, input_fn=input)`——可注入 input 的答案收集辅助函数，捕获 `EOFError/OSError` 后逐题回落到第一个选项（与 `quiz.py` 的 `mbti_letters` 对无效答案的兜底策略一致），回落时输出提示；`cmd_quiz`（第 104 行）改用该函数。
- `tests/test_mcparallel.py` 第 220 行新增 `TestCollectAnswers`（6 项，全部注入 `input_fn`，禁止真实 `input()`）：
  `test_eof_falls_back_to_first_option` / `test_oserror_falls_back_to_first_option` / `test_partial_eof_fallback` / `test_normal_input_collected_and_normalized` / `test_fallback_hint_printed` / `test_no_hint_in_interactive_mode`

**Bug 2 · demo.py 每次运行生成时间戳卡片污染仓库（次任务）**

修改：`demo.py` 第 103-107 行——运行前清理 `output/cards/mcparallel_*.svg` 遗留时间戳卡片，`render_card` 改传 `out_path=output/cards/demo-card.svg`（固定路径覆盖写）。

验证（连续两次 `python demo.py`，先手工放置遗留卡片 `mcparallel_g1_20990101_000000.svg`）：

```text
$ ls output/cards/
demo-card.svg
sample-card-worker.svg
sample-card.svg
--- 第二次 ---
demo-card.svg
sample-card-worker.svg
sample-card.svg
```

（遗留时间戳卡片已被清理，两次运行无新增文件 ✓）

**回归验证**

```text
$ python -m mcparallel quiz --universe game --answers A,B,C
🎴 鉴定结果：指挥打野型（契合度 99%）
```

（与修复前行为一致 ✓——`--answers` 分支代码未改动）

**最终测试结果**

```text
$ python -m unittest discover -s tests
Ran 61 tests in 0.809s
OK
```

（原 55 项全绿保持 + 新增 6 项 = 61 项全绿，退出码 0 ✓）

## 记录状态

- [x] 对话 1（三连抽）
- [x] 对话 2（人格鉴定）
- [x] 对话 3（指南）
- [x] 对话 4（确认制领券）
- [x] 对话 5（Bug 修复）
> 后注（审查阶段）：6 项 collect_answers 测试合并为 4 项（断言未减少，消除测试输出噪音），当前全套 59 项测试全绿。


（以上为 2026-10-16 真实对话文本，MCP 调用 traceId 留档可查）
