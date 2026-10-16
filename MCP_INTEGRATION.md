# MCP Integration（麦当劳 MCP 集成说明）

本项目（麦门平行宇宙 McParallel）**真实使用麦当劳官方 MCP Server**（`mcd-mcp` v1.0.0，`https://mcp.mcd.cn`，Streamable HTTP，Bearer Token 认证）作为唯一的数据与业务能力来源。菜品、价格、营养、门店、优惠券、活动等全部信息来自实时 MCP 调用，不使用任何写死的菜单数据。

## 使用的 MCP Server

| 项目 | 值 |
|---|---|
| Server | `mcd-mcp` v1.0.0（麦当劳中国官方，open.mcd.cn） |
| 接入地址 | `https://mcp.mcd.cn` |
| 协议 | Streamable HTTP（MCP `2025-03-26`） |
| 认证 | MCP Token（Bearer），于 [open.mcd.cn](https://open.mcd.cn) 申请 |

## 使用的 Tool 清单与业务价值

| Tool | 用途 | 业务价值 |
|---|---|---|
| `query-nearby-stores` | 按城市定位门店，获取 `storeCode` | 所有推荐落到用户真实可点的门店 |
| `query-meals` | 实时菜单（实测 98 单品：名称/价格/图片/官方分类标签） | 三池分类（主食/小吃/饮品）与全部推荐的候选池来自实时在售菜单 |
| `list-nutrition-foods` | 160 条餐品营养成分 | 菜品五维标签矩阵与指南人群定制全部由真实营养数据量化推导 |
| `query-meal-detail` | 餐品组成与**随心配 1+1 蓝区/粉区结构** | 优惠引擎的 1+1 路径（实测蓝区 7 选 1 × 粉区 10 选 1） |
| `calculate-price` | 实时算价（单位：分，含优惠） | 三路径比价的"直接单点"实算；所有展示价格真实可核 |
| `query-store-coupons` | 门店可用券 | 抽卡与推荐结果自动叠加券提示 |
| `available-coupons` | 麦麦省可领券 | 指南领券策略入口（领取动作须用户确认） |
| `campaign-calendar` | 当月营销活动日历 | 指南"打工人篇"限时活动联动 |
| `query-lottery-info` | 积分抽奖奖品池与消耗（不执行抽奖） | 真抽卡模式展示（抽奖须用户明确确认后才可调用 `draw-lottery`，本项目 CLI 不自动执行） |
| `query-my-account` | 积分余额 | 抽卡前积分提示（仅用户查询时） |
| `order-list` | 常点历史（可选，需用户明示授权） | 逆向鉴定的辅助画像来源 |

## 调用流程（三合一）

```
【板块一 · 三连抽 + 最优购买方案引擎】
用户抽 3 张卡（主食/小吃/饮品池，由 query-meals 官方分类自动归档，非食品已过滤）
  → query-nearby-stores ──→ storeCode
  → query-meals ──→ 实时菜单三池
  → （已鉴定用户）人格向量加权抽取：池内中心化余弦归一化平方加权
  → query-meal-detail(随心配SKU) ──→ 解析 1+1 蓝区/粉区（code+名称双轨匹配，
      因随心配子项 code 与菜单单品 code 不属同一体系，实测菜单可乐 9900008751 vs 粉区可乐中杯 3050）
  → 三路径比价：
      ① calculate-price 三件直接单点（实算，单位分→元）
      ② 主食∈蓝区 且 小吃/饮品∈粉区 → 随心配标价 + 剩余单点
      ③ query-store-coupons 可用券提示（叠加实付以下单核价为准，不参与最优判定——诚实边界）
  → 输出最省钱路径 + 共省金额 + 场景签文案
  → （可选真抽卡）query-lottery-info 展示奖品池与消耗 → 用户明确确认 → draw-lottery

【板块二 · 麦人格鉴定（六宇宙 46 人格）】
逆向（主入口）：选宇宙 → 3 道场景题（麦门16型为 4 道字母题）
  → 答案增量聚合为口味五维向量（刺激/续航/性价比/精致/稳健）
  → 与人格库中心化余弦匹配 → 身份卡（契合度%）
正向（二级入口）：直接选人格原型 → "TA 会吃什么"
  → match_items 五维匹配 Top3（list-nutrition-foods 营养量化的菜品标签矩阵）
  → calculate-price 适配套餐实算 + query-store-coupons 叠券提示
  → LLM 生成角色化文案（黑名单过滤：竞品品牌/真人名/角色名/占卜用语），
     未配置 LLM 时退回确定性模板，保证零依赖可运行
  → SVG 身份卡渲染（雷达图 + 五维 + 套餐 + 专属省钱 tip）

【板块三 · 高性价比指南】
  → list-nutrition-foods 人群定制计算：
      健身高碳日（碳水总量排序）/ 低碳日（碳水≤40g 中蛋白最高）/ 练后（≤800kcal 蛋白最高）
      减脂 ≤500 kcal 清单（蛋白密度排序）；学生党 kcal/元排行 + 预算贪心搜索
  → calculate-price 实算验证省钱方案
  → available-coupons 券策略（auto-bind-coupons 领取须用户确认）
  → campaign-calendar 限时活动联动 / query-my-account 积分提示
  → 生成 GUIDE.md（数字全部来自上述实时数据）
```

## 工程模式（借鉴榜单头部项目并验证）

- **取数交给 MCP，算术交给代码，表达交给 LLM**：标签矩阵/匹配/优惠引擎全部为可单测的确定性代码（43 个单元测试），LLM 仅生成文案且输出过黑名单过滤。
- **在线/离线双模式**：`fixtures/` 录制真实 MCP 响应，无 Token 可跑通全流程（`python demo.py`）；参数敏感工具（算价/详情）离线必须精确命中录制，防止错误数据兜底。
- **诚实边界**：价格来源逐项标注（实算/估算）；券路径不参与最优判定；未验证能力在能力矩阵中如实声明。

## 安全与合规

- Token 仅通过环境变量 `MCD_MCP_TOKEN` 注入，仓库内 `mcp-config.example.json` 只含 `${MCD_MCP_TOKEN}` 占位符，无任何真实凭证。
- 变更类 Tool（`create-order` / `cancel-order` / `draw-lottery` / `auto-bind-coupons` / `mall-create-order` 等）一律确认制，本项目 CLI 与 Skill 均不自动执行。
- 探测原始数据（含账号隐私）不进入仓库（见 `.gitignore`）。
- 人格文案层带合规黑名单（竞品品牌/真人名/角色名/占卜用语），命中即拦截换兜底模板。

> 工具清单实测详情与传参规则见 [docs/mcp-tools.md](docs/mcp-tools.md)；能力边界见 [docs/capability-matrix.md](docs/capability-matrix.md)。
