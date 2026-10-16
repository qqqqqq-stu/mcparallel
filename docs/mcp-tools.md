# 麦当劳 MCP 工具清单与数据结构（实测版）

> 2026-10-15 用真实 MCP Token 对 `https://mcp.mcd.cn` 实测整理。
> 原始探测脚本见 `scripts/mcp_probe.py` / `scripts/mcp_batch_probe.py`，原始响应存于 `docs/probe/`（含账号隐私，已 gitignore，仅本地参考）。

## 服务器信息

| 项目 | 值 |
|---|---|
| Server | `mcd-mcp` v1.0.0 |
| 地址 | `https://mcd.mcd.cn` |
| 传输 | Streamable HTTP |
| 协议版本 | `2025-03-26`（实测可用） |
| 认证 | `Authorization: Bearer <MCP_TOKEN>`（[open.mcd.cn](https://open.mcd.cn) 申请） |
| 限流 | 每 Token 600 次/分钟，超限返回 429；Token 无效返回 401 |

**响应结构要点（重要）**：每个工具返回两部分——
- `result.content[0].text`：给 LLM 看的字段说明 + 展示格式要求（内嵌原始 JSON）
- `result.structuredContent.data`：**纯 JSON 数据，程序处理请用这个**

## 工具总览（35 个，按功能分组）

标记 `[写]` 的工具会改变账号/订单状态，自动化流程中慎用；其余为只读。

### 菜单与营养（本项目核心数据源）
| 工具 | 关键参数 | 说明 |
|---|---|---|
| `query-meals` | `storeCode*` `orderType*`(1到店/2外送) `beType*`(1到店/2麦乐送/5得来速/6团餐) | 全量菜单：`categories`(15分类) + `meals`(98单品，code→{name,image,currentPrice,originalPrice,canWithOrder}) + `frequent`。分类和单品自带官方标签（如"爆款"） |
| `query-meal-detail` | `storeCode*` `orderType*` `beType*` `code*` | 餐品组成：`rounds`(套餐选配轮次) + `modification`(特调项，如巨无霸酱/吉士/生菜，含 selectedKey/unselectedKey 传参规则) |
| `list-nutrition-foods` | 无 | **160 条营养成分**：productName, energyKj, energyKcal, protein, fat, carbohydrate, sodium, calcium |

### 门店
| 工具 | 关键参数 | 说明 |
|---|---|---|
| `query-nearby-stores` | `beType*`(1自提/5得来速) `searchType*`(1收藏/2按位置) `city` `keyword` | 返回 storeName/address/distance/**storeCode**/beCode/reservation(预约时段)。**实测坑**：searchType=2 只传 `city` 会报错 600058，必须 `city` + `keyword` 同传 |
| `delivery-query-addresses` | 无 | 外送地址簿（addressId/联系人/电话/完整地址） |
| `delivery-query-stores` | `addressId*` `beType*` | 按地址查可配送门店 |
| `delivery-create-address` `[写]` | 地址信息 | 创建外送地址 |
| `query-meal-assistance` | `storeCode*` | 企业团餐助餐服务 |

### 下单与算价
| 工具 | 关键参数 | 说明 |
|---|---|---|
| `calculate-price` | `storeCode*` `orderType*` `beType*` `items*`(productCode+quantity) | 算价（**单位为分**），返回优惠/取餐方式 takeWayList；实测巨无霸=2550分 |
| `create-order` `[写]` | 同上 + 取餐方式 | 真实下单 |
| `query-order` | `orderId*` | 订单详情/配送进度 |
| `order-list` | 无 | 历史订单（含 productCode/productName/quantity，可用于"常点分析"） |
| `cancel-order` `[写]` | `orderId*` `cancelReasonCode*`(1改主意/2重复下单/3点错/4地址电话错/5送达时间错) | 取消订单 |

### 优惠券与会员
| 工具 | 关键参数 | 说明 |
|---|---|---|
| `available-coupons` | 无 | 麦麦省可领券列表（couponName/couponImage/couponStatus/label） |
| `auto-bind-coupons` `[写]` | 无 | 一键领取全部可领券 |
| `query-store-coupons` | `storeCode*` `orderType*` `beType*` | 指定门店+订单类型可用券 |
| `query-my-coupons` | `page` `pageSize` | 我的卡包券 |
| `query-my-account` | 无 | 积分账户（可用/将过期积分等） |

### 积分商城
| 工具 | 说明 |
|---|---|
| `mall-points-products` | 积分可兑换列表（商品券/实物/周边/礼品卡/各类派对活动） |
| `mall-product-detail(spuId*)` | 兑换商品 SKU 详情 |
| `mall-create-order` `[写]` | 积分兑换下单 |
| `mall-order-list` / `mall-order-detail` | 商城订单查询 |

### 积分抽奖（"麦门抽卡"可用）
| 工具 | 说明 |
|---|---|
| `query-lottery-info` | 抽奖活动信息（活动名/消耗积分/剩余次数/奖品列表，**不执行抽奖**） |
| `draw-lottery` `[写]` | 执行一次抽奖。官方要求：必须先向用户展示 drawDecision.nextConsumption 并获得明确确认后才能调用 |
| `query-my-prizes` | 我的奖品 |

### 主题活动（派对/品鉴会）
`query-party-city` → `query-party-store` → `query-party-store-date` → `query-party-store-session` → `party-order-create` `[写]`（生日/主题派对/麦麦体验营/品鉴会/读书会预约链路）；另有 `query-promotions`（企业团餐满减满折）。

### 辅助
| 工具 | 说明 |
|---|---|
| `now-time-info` | 服务器当前时间 |
| `campaign-calendar` | 当月营销活动日历（活动标题/图文/跳转链接，可查往期与未来） |
| `query-survey-coupon(orderId*)` | 订单满意度答卷与关联奖券 |

## 已验证的调用链

```
① 菜单链路（正向推荐的数据底座）
   query-nearby-stores(beType=1, searchType=2, city="上海市")
     → 取 storeCode（实测 1450713 上海人民广场附近店）
   query-meals(storeCode, orderType=1, beType=1) → 98 单品 + 价格 + 图片 + 官方标签
   list-nutrition-foods() → 160 条营养成分（与菜单按 productName 模糊关联）

② 详情/算价链路（"一键同款加购"）
   query-meal-detail(storeCode, orderType=1, beType=1, code="1100")
     → 巨无霸特调项（酱/吉士/生菜/酸黄瓜/洋葱粒）+ selectedKey/unselectedKey 规则
   calculate-price(storeCode, orderType=1, beType=1, items=[{productCode:"1100",quantity:1}])
     → 现价 2550 分（¥25.50）、优惠明细、取餐方式

③ 情报链路（情绪/活动/省钱文案素材）
   campaign-calendar() / available-coupons() / query-store-coupons(...) / query-lottery-info()
```

## 传参规则备忘

1. **beType 语义**：1-到店取餐，2-麦乐送到家，5-得来速，6-企业团餐；`orderType`：1-到店（含得来速），2-外送。
2. **到店自提（beType=1）不传 beCode**，传了会报错；得来速/外送/团餐必须传（来自门店查询结果）。
3. **价格单位是分**（2550 = ¥25.50），展示时记得除以 100。
4. `reservationDate` 仅预约场景传，格式 `yyyy-MM-dd HH:mm`。
5. 特调（modification）传参规则：`unselectedKey` 不为空的特调组，组内**所有**项都要传给算价/下单接口——选中项用 `selectedKey`，未选中项用 `unselectedKey`。
6. `draw-lottery` 官方约束：必须先展示 `query-lottery-info` 返回的 `drawDecision.nextConsumption`（如"本次将消耗 24 积分"）并获用户明确确认后才可调用。
