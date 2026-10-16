# 🍔 麦门平行宇宙 McParallel

> 基于麦当劳官方 MCP 的**三合一** AI 点餐 Skill —— **你点什么，决定你是谁。**

**当点麦当劳变成一场人格鉴定。** 不知道吃什么？抽三张牌（还自动帮你算最优惠买法）。想知道你是谁？六大人格宇宙 46 种人格等你鉴定，生成可分享的麦门身份卡。想吃得明白？健身高碳日、减脂 500 大卡线、学生党省钱数学，全部由真实数据算给你看。

> 🏆 本项目参加 [麦当劳程序员节创意开发大赛](https://github.com/M-China/mcd-developer-innovation-challenge)。全部餐品/价格/营养/门店/优惠券数据来自 [麦当劳官方 MCP](https://open.mcd.cn) 实时调用——**命运可以随机，价格必须真实。**

## 三合一 · 三层咬合（不是三个功能，是一个产品）

决定吃什么（抽卡）↔ 你是谁（人格）↔ 怎么吃最值（指南）——三层共享同一个数据底座（菜品五维标签矩阵）与同一个用户状态（人格向量），收敛为一张可分享的麦门身份卡。鉴定出的人格实时加权你的抽卡池，身份卡自带专属省钱攻略，任一入口进入都能走完全程。

| 层 | 一句话 | 怎么实现 |
|---|---|---|
| 🃏 **决定层** · 三连抽 | 主食/小吃/饮品各抽一张（人格向量加权），自动计算**最优惠购买方案**：直接单点 vs **1+1 随心配** vs 用券，实时算价比对 | `query-meals` 三池 × `query-meal-detail` 蓝粉区解析 × `calculate-price` 实算 × `query-store-coupons` |
| 🧬 **身份层** · 麦人格鉴定 | 六大宇宙任你测（🍔 单品人格 × 🎮 游戏战术 × 💼 打工人 × 🧠 麦门16型 × 🎬 创作者 × 🎤 主播），3 道场景题出**五维雷达身份卡** + 适配套餐 + 专属省钱 tip | 营养数据量化五维标签矩阵 × 中心化余弦双向匹配 × LLM 文案（黑名单过滤）× SVG 卡片渲染 |
| 📖 **实用层** · 高性价比指南 | 健身高碳/低碳日菜单、减脂 500 大卡线、学生党 kcal/元排行与预算搜索、打工人活动日历——**每个数字都是算出来的** → [GUIDE.md](GUIDE.md) | `list-nutrition-foods` 160 条营养数据 × `calculate-price` 实算 × 券策略 × `campaign-calendar` |

### 麦门身份卡（可分享的社交货币）

```bash
python -m mcparallel card --universe game --answers A,A,A
```

生成 1200×1680 SVG 身份卡（GitHub 原生可渲染）：五维雷达图（你的口味向量 vs 人格画像叠加）+ 契合度 + 实时适配套餐 + 专属省钱 tip + 人格推荐语。示例见 [output/cards/](output/cards/)。

## 🖥️ 30 秒看效果

```text
🍔 麦门平行宇宙 McParallel · Demo（数据：麦当劳官方 MCP 实时/录制）

① 统一数据底座
   主食池: 47 个单品 | 小吃池: 28 | 饮品池: 17 | 随心配池: 2（徽章/玩具/酱料已自动过滤）
   营养数据关联: 50/98 个单品命中官方营养表 | 人格原型库: 46 个 / 6 大宇宙

② 板块一 · 三连抽「今天吃什么」（人格加权 + 优惠引擎）
🎴 场景签：开工运 —— 新的一天，先把胃填满，再填 KPI。
   [主食] 麦香鸡套餐 ¥28.0 / [小吃] 鸡薯双全盒 ¥15.9 / [饮品] 多汁柠柠 ¥12.0
   （已按「峡谷刺客型」的口味向量加权抽取）
💰 [直接单点] ¥55.9（菜单价估算） 🎫 可用券：中薯条买一送一、王牌小食拼
   → 1+1 路径实测：麦香鱼+可乐+巨无霸 直接 ¥57.5 vs 随心配路径 ¥39.4，共省 ¥18.1

③ 板块二 · 麦人格鉴定（3 道场景题）
Q1. 决胜局最后十秒，你选？ → 梭哈！赌一把大的
🎴 鉴定结果：极限翻盘型（契合度 99%）「逆风才好玩，翻盘才叫赢」
   TA 会点什么：辣么快乐套餐 ¥24.0 / 韩式甜辣酱鸡块 ¥19.9 / 麦辣鸡翅 ¥15.0
   💡 专属省钱 tip：麦辣系列走 1+1 蓝区，饮料换无糖可乐，刺激不减、钱包减负。

④ 板块三 · 高性价比指南（预算定制）
   预算 ¥25 吃饱方案（≥500 kcal）：那么大鸡排 ¥14.0 + 燕麦奶铁 ¥9.9 = ¥23.9 / 517 kcal ✓
```

## 快速开始

```bash
# 30 秒离线体验（零依赖、无需 Token，回放真实 MCP 录制数据）
python demo.py

# 完整 CLI（三合一全流程）
python -m mcparallel draw --persona 峡谷刺客型     # 人格加权三连抽 + 优惠引擎
python -m mcparallel quiz --universe game          # 交互式人格鉴定
python -m mcparallel forward --persona 摸鱼艺术家型  # TA 会吃什么
python -m mcparallel reverse --items 巨无霸,麦乐鸡,可乐  # 常点组合鉴定
python -m mcparallel --online history              # 常点订单画像（需本人 Token，只读不落盘）
python -m mcparallel guide --budget 25             # 25 元怎么吃最饱
python -m mcparallel card --universe worker        # 生成 SVG 身份卡

# 安装为 WorkBuddy 技能（配合 MCP 连接器）
cp -r skills/mcparallel ~/.workbuddy/skills/       # Windows: %USERPROFILE%\.workbuddy\skills\

# 在线模式（实时调用麦当劳 MCP）
cp .env.example .env    # 填入你在 https://open.mcd.cn 申请的 MCD_MCP_TOKEN
python demo.py --online

# 测试（59 项全绿）
python -m unittest discover -s tests
```

MCP 客户端配置见 [mcp-config.example.json](mcp-config.example.json)；WorkBuddy 技能定义见 [SKILL.md](SKILL.md)。MIT License，见 [LICENSE](LICENSE)。

## 技术架构

```
用户输入(抽卡 / 人格测试 / 指南查询)
        │
        ▼
┌──────────────────────────────────────┐
│  统一数据底座                          │
│  ├─ 菜品五维标签矩阵(160条营养数据量化) │
│  ├─ 人格原型库(六宇宙 46 人格)         │
│  ├─ 优惠规则库(1+1蓝粉区/门店券/活动)   │
│  └─ 用户状态(人格向量，贯穿三层)        │
├──────────────────────────────────────┤
│  确定性引擎层(纯标准库，59项单测覆盖)    │
│  ├─ 三池分类 + 人格加权抽卡             │
│  ├─ 五维双向匹配(中心化余弦)            │
│  └─ 优惠引擎(直接购/1+1/用券三路径比价) │
├──────────────────────────────────────┤
│  表达层                               │
│  ├─ LLM Prompt(黑名单过滤，模板兜底)   │
│  └─ SVG 身份卡渲染(雷达图程序排版)      │
└──────────────────┬───────────────────┘
                   │ MCP (Streamable HTTP)
                   ▼
      麦当劳官方 MCP Server (mcp.mcd.cn)
      门店 / 菜单 / 营养 / 算价 / 优惠券 / 活动 / 抽奖
```

- **取数交给 MCP，算术交给代码，表达交给 LLM**：标签/匹配/优惠全为可单测的确定性代码，LLM 只写文案且过黑名单（竞品/真人/角色名/占卜用语）。
- **零门槛**：纯 Python 标准库（零第三方依赖）+ fixtures 离线回放，无需 Token 跑通全流程。
- **诚实边界**：价格来源逐项标注（实算/估算）；券不参与最优判定；未验证能力如实声明（见[能力矩阵](docs/capability-matrix.md)）。
- **实测彩蛋**：随心配子项的 code 与菜单单品不是一套体系（菜单可乐 `9900008751` vs 粉区可乐中杯 `3050`），优惠引擎用 code+名称双轨匹配解决——详见 [docs/mcp-tools.md](docs/mcp-tools.md)。

## 项目结构

```
├── README.md / GUIDE.md / SKILL.md    # 项目门面 / 实用指南 / WorkBuddy 技能定义
├── CONTEST_DECLARATION.md             # 参赛声明（官方模板原样）
├── MCP_INTEGRATION.md                 # MCP 集成说明（比赛必备）
├── mcp-config.example.json            # 脱敏 MCP 配置（仅环境变量占位符）
├── workbuddy.md                       # WorkBuddy 对话上下文（专项奖）
├── demo.py                            # 30 秒离线 Demo
├── mcparallel/                        # 引擎包（标准库零依赖）
│   ├── mcp_client.py                  # MCP 客户端：在线 + fixtures 离线
│   ├── menu.py / tag_matrix.py        # 三池分类 / 五维标签矩阵
│   ├── personas.py / quiz.py          # 人格库 / 场景题流
│   ├── matching.py / draw.py          # 双向匹配 / 三连抽
│   ├── savings.py / guide.py          # 优惠引擎 / 指南引擎
│   ├── llm_copy.py / card.py / cli.py # 文案层 / 身份卡 / 统一 CLI
├── data/                              # 人格库与题库（策划可直接改）
├── fixtures/                          # 真实 MCP 响应录制（离线回放）
├── tests/                             # 59 项单元测试
└── docs/                              # 工具实测清单 / 能力矩阵（内部策划文档不入库）
```

## 开发状态

- [x] MCP 全量工具探测与全链路验证（35 tools）
- [x] 统一数据底座：三池分类 × 五维标签矩阵 × 六宇宙 46 人格库 × 双向匹配
- [x] 板块一：三连抽（人格加权）+ 最优购买方案引擎（1+1 路径实测省 ¥18.1）
- [x] 板块二：场景题流 + LLM 文案层（黑名单）+ SVG 身份卡渲染
- [x] 板块三：高性价比指南引擎 + GUIDE.md 生成
- [x] 统一 CLI + 零 Token 离线 Demo + 59 项单元测试
- [x] WorkBuddy SKILL.md + 比赛必备四件套
- [x] WorkBuddy 真实联调（4 段对话实测通过，记录已回填 [workbuddy.md](workbuddy.md)）
- [ ] 传播物料（Demo GIF / 短视频 / 发布帖）

## 声明

本项目为麦当劳程序员节创意开发大赛参赛作品，由参赛者独立开发，非官方产品。输出的餐品信息、价格及供应状态以麦当劳官方渠道的实时结果为准；推荐与人格内容仅供娱乐参考，健康饮食请遵循均衡膳食原则。
