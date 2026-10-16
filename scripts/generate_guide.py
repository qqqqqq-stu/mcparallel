#!/usr/bin/env python3
"""生成 GUIDE.md《麦门高性价比指南》：数据由真实 MCP（或 fixtures）计算，框架文案手写。

用法:
    python scripts/generate_guide.py            # 离线（fixtures 数据）
    python scripts/generate_guide.py --online   # 在线实时数据
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mcparallel.guide import campaign_titles, fat_loss_list, fitness_plan, kcal_per_yuan
from mcparallel.menu import DEFAULT_STORE, attach_nutrition, load_menu, load_nutrition
from mcparallel.mcp_client import MCPClient
from mcparallel.savings import SavingsEngine
from mcparallel.tag_matrix import build_matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    online = "--online" in sys.argv
    client = MCPClient(offline=not online)
    nutrition = load_nutrition(client)
    items = build_matrix(attach_nutrition(load_menu(client), nutrition), nutrition)
    engine = SavingsEngine(client, items, DEFAULT_STORE)
    now = time.strftime("%Y-%m-%d %H:%M")

    fit = fitness_plan(nutrition)
    fat = fat_loss_list(nutrition)
    kpy = kcal_per_yuan(items)[:10]
    events = campaign_titles(client)
    zones = engine.one_plus_one_zones()
    zone = zones[0] if zones else None

    def table(rows, headers):
        head = "| " + " | ".join(headers) + " |"
        sep = "|" + "|".join(["---"] * len(headers)) + "|"
        body = "\n".join("| " + " | ".join(str(c) for c in r) + " |" for r in rows)
        return "\n".join([head, sep, body])

    fit_sections = []
    for title in ("高碳日", "低碳日（高蛋白优先）", "练后快充（蛋白+适度碳水）"):
        rows = [(r["name"], f'{r["kcal"]} kcal', f'碳水 {r["carb"]}g', f'蛋白 {r["protein"]}g') for r in fit[title][:6]]
        fit_sections.append(f"#### {title}\n\n{table(rows, ['单品', '热量', '碳水', '蛋白'])}")

    fat_rows = [(r["name"], f'{int(r["kcal"])} kcal', f'{r["protein"]}g', f'{r["fat"]}g') for r in fat]
    kpy_rows = [(r["name"], f'¥{r["price"]}', f'{r["kcal"]} kcal', f'{r["kcal_per_yuan"]}') for r in kpy]

    zone_section = "（当前门店暂无随心配数据）"
    if zone:
        blue = "、".join(c["name"] for c in zone["blue"])
        pink = "、".join(c["name"] for c in zone["pink"])
        zone_section = (
            f"当前实测（{zone['sku']['name']} ¥{zone['sku']['price']}）：\n\n"
            f"- **蓝区（7 选 1）**：{blue}\n- **粉区（10 选 1）**：{pink}\n\n"
            f"省钱算术：麦香鱼 ¥22.5 + 可乐 ¥9.5 = ¥32.0，走随心配两件只要 ¥{zone['sku']['price']}，"
            f"**单这一步省 ¥{round(22.5 + 9.5 - zone['sku']['price'], 1)}**。前提：这两件都在蓝/粉区里。"
        )

    events_section = "\n".join(f"- {t}" for t in events) if events else "（暂无活动数据，以麦当劳 App 为准）"

    md = f"""# 📖 麦门高性价比指南

> **怎么吃麦当劳，才对得起钱包和身体。**
> 本指南所有数字由**麦当劳官方 MCP 实时数据**计算（菜单 {len(items)} 项 × 营养表 {len(nutrition)} 条），
> 生成时间 {now}（{'在线实时' if online else '离线录制数据'}）。价格与供应以官方渠道实时为准。

## 一、随心配 1+1：官方发的"组合数学题"

{zone_section}

## 二、健身人群：高碳日 / 低碳日 / 练后

{fit_sections[0]}

{fit_sections[1]}

{fit_sections[2]}

> 高碳日优先碳水总量，低碳日在碳水 ≤40g 里挑蛋白最高，练后快充控制在 800 kcal 内。
> 表内单品来自官方营养档案（160 条），部分单品可能不在当前时段在售菜单，以 App 实时为准。

## 三、减脂人群：500 大卡以内怎么吃

{table(fat_rows, ['单品（≤500 kcal）', '热量', '蛋白质', '脂肪'])}

**放纵日策略**：想痛快一顿，把它留给套餐而非单点堆叠——套餐的结构性折扣意味着同样的满足感花更少的钱，心理负担也小一半。官方 **500 大卡套餐** 分类本身就是为克制场景准备的。

## 四、学生党：每一块钱的热量效率

{table(kpy_rows, ['单品', '价格', '热量', 'kcal/元'])}

**组合数学**：随心配 ¥13.9-14.9 两件是学生党的底仓；两个人各点一份随心配比拼单大套餐更容易控制预算。
交互定制：`python -m mcparallel guide --budget 25` 实时算"25 元怎么吃最饱"。

## 五、打工人：跟着活动日历吃

{events_section}

## 六、健康与边界声明

- 本指南为参赛作品内容，**非麦当劳官方产品**；餐品信息、价格及供应状态以麦当劳官方渠道实时结果为准。
- 营养数据来自官方营养表，**单一餐品 ≠ 一整天的饮食**；健身/减脂方案仅供参考，特殊健康状况请遵医嘱。
- 快乐也是营养的一部分——偶尔的放纵餐不需要愧疚，指南只是让每一次选择都明明白白。
"""

    out = os.path.join(ROOT, "GUIDE.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"GUIDE.md 已生成（{len(md)} 字符）-> {out}")


if __name__ == "__main__":
    main()
