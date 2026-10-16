"""表达层 · LLM 文案生成：Prompt 构建 + 合规黑名单过滤 + 确定性模板兜底。

架构原则（借鉴头部竞品）：算术交给代码，表达交给 LLM。
- 配置了 OPENAI_API_KEY（兼容 OpenAI 协议的接口，含 OPENAI_BASE_URL）时调用 LLM；
- 未配置时退回确定性模板拼接，保证 Demo 零依赖零密钥可运行；
- 无论哪条路径，输出一律过黑名单过滤（角色名/真人名/竞品品牌/占卜用语）。
"""
from __future__ import annotations

import json
import os
import urllib.request

from .tag_matrix import DIM_ZH

# ---------- 合规黑名单（LLM 输出防线，宁可误杀不可漏过） ----------

# 竞品品牌（比赛规则禁止与其他品牌对比/提及）
COMPETITOR_BRANDS = [
    "肯德基", "KFC", "汉堡王", "德克士", "塔斯汀", "华莱士", "必胜客", "赛百味",
    " Subway", "麦当劳的对手", "金色拱门不如",
]
# 真人名（主播/KOL/明星，比赛规则与民法典人格权红线）
REAL_PEOPLE = [
    "大司马", "张大仙", "PDD", "何同学", "影视飓风", "手工耿", "旭旭宝宝", "冯提莫",
    "周淑怡", "孤影", "梦泪", "Uzi", "Faker",
]
# 游戏角色名（著作权红线，人格一律用原创原型表达）
GAME_CHARACTERS = [
    "李白", "亚索", "雷电将军", "捷风", "韩信", "貂蝉", "鲁班七号", "妲己",
    "提莫", "盖伦", "赵信", "永恩", "菲恩", "阿莎",
]
# 占卜/迷信用语（比赛规则明文禁止）
DIVINATION_WORDS = ["占卜", "算命", "塔罗", "牌阵", "预知", "天命", "转运", "命中注定", "玄学"]

BLOCKLIST = [
    ("竞品品牌", COMPETITOR_BRANDS),
    ("真人名字", REAL_PEOPLE),
    ("游戏角色名", GAME_CHARACTERS),
    ("占卜用语", DIVINATION_WORDS),
]

SYSTEM_PROMPT = """你是「麦门平行宇宙」的人格文案生成器。根据给定的人格原型与餐品数据，生成一句短小精悍、带梗但克制的中文推荐文案。

铁律（违反即重写）：
1. 只谈麦当劳（麦门），绝不提及其他品牌。
2. 绝不出现任何真实人物名、游戏角色名、作品名——人格一律用给定的原创原型设定表达。
3. 绝不出现占卜、算命、运势预测类表述——这是纯娱乐内容。
4. 不宣扬暴饮暴食、不美化熬夜；提到深夜场景时用"犒劳自己"的框架。
5. 输出不超过 60 字，不解释规则本身。"""


def check_text(text: str) -> list[tuple[str, str]]:
    """返回命中的黑名单项 [(类别, 词)]。空列表 = 安全。"""
    hits = []
    for category, words in BLOCKLIST:
        for w in words:
            if w in text:
                hits.append((category, w))
    return hits


def filter_text(text: str) -> str:
    """黑名单命中的文案直接丢弃，换兜底模板（不替换词，避免语义漂移）。"""
    return text if not check_text(text) else ""


def build_prompt(persona: dict, items: list[dict], scene: dict | None = None) -> str:
    """构建完整 user prompt（含真实数据与人格设定）。"""
    item_lines = [
        f"- {it['name']}（¥{it['price']}，五维：{ {DIM_ZH[d]: it['vector'][d] for d in it['vector']} }）"
        for it in items
    ]
    scene_line = f"\n当前场景签：{scene['name']}（{scene['copy']}）" if scene else ""
    return (
        f"人格原型：{persona['name']}（宇宙：{persona['universe']}）\n"
        f"人设关键词：{'、'.join(persona['keywords'])}\n"
        f"语气要求：{persona['style_note']}\n"
        f"参考口吻：{persona['sample_line']}\n"
        f"\n适配电品（真实 MCP 数据）：\n" + "\n".join(item_lines)
        + scene_line
        + "\n\n请以该人格的口吻，为这套餐写一句推荐文案。"
    )


# ---------- 确定性模板兜底 ----------

_DIM_HIGHLIGHT = {
    "thrill": "够劲",
    "sustain": "扛饿",
    "value": "划算",
    "refine": "体面",
    "steady": "温和",
}


def _top_dims(vector: dict, n: int = 2) -> list[str]:
    return sorted(vector, key=lambda d: -vector[d])[:n]


def template_copy(persona: dict, items: list[dict], scene: dict | None = None) -> str:
    """零依赖兜底文案：由人格设定与餐品特征确定性拼接。"""
    main = items[0] if items else None
    parts = [persona["sample_line"].rstrip("。")]
    if main:
        traits = "、".join(_DIM_HIGHLIGHT[d] for d in _top_dims(main["vector"]))
        parts.append(f"{main['name']}这套{traits}，正好长在你的口味雷达上")
    if len(items) > 1:
        parts.append(f"再配一份{items[1]['name']}，今日份的{persona['name'].rstrip('型')}含量达标")
    if scene:
        parts.append(f"【{scene['name']}】")
    return "。".join(parts) + "。"


# ---------- LLM 调用（可选） ----------

def _llm_available() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY"))


def _call_llm(system: str, user: str) -> str:
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("MCD_LLM_MODEL", "glm-4.6")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.8,
        "max_tokens": 120,
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
    )
    req.add_header("Authorization", f"Bearer {os.environ['OPENAI_API_KEY']}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


def generate_copy(persona: dict, items: list[dict], scene: dict | None = None) -> dict:
    """生成人格化推荐文案。返回 {text, source, blocked}。

    LLM 输出过黑名单；命中即丢弃换模板，绝不放行。
    """
    fallback = template_copy(persona, items, scene)
    if not _llm_available():
        return {"text": fallback, "source": "确定性模板（未配置 LLM）", "blocked": []}
    try:
        raw = _call_llm(SYSTEM_PROMPT, build_prompt(persona, items, scene))
    except Exception as e:  # noqa: BLE001 - LLM 任何故障都退模板，不影响主流程
        return {"text": fallback, "source": f"确定性模板（LLM 调用失败：{type(e).__name__}）", "blocked": []}
    hits = check_text(raw)
    if hits:
        return {"text": fallback, "source": "确定性模板（LLM 输出命中黑名单，已拦截）", "blocked": hits}
    return {"text": raw, "source": f"LLM（{os.environ.get('MCD_LLM_MODEL', 'glm-4.6')}）", "blocked": []}
