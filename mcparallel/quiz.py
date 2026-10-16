"""板块二 · 场景题流：3 道题（麦门16型为 4 道字母题）→ 五维向量 → 人格鉴定。

题目全部原创；选项增量推到全菜单均值基线上（普通人起点），
答完得到用户口味向量，再走 match_personas 鉴定。
"""
from __future__ import annotations

import json
import os

from .tag_matrix import DIMS

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_quiz() -> dict:
    with open(os.path.join(DATA_DIR, "quiz.json"), encoding="utf-8") as f:
        return json.load(f)


def quiz_vector(universe: str, answers: list[str], base: dict) -> dict:
    """按答案聚合五维向量。answers 为选项字母列表（如 ["A","B","C"]）。

    非交互场景答案不足时自动选每题第一个选项（保持确定性）。
    """
    questions = load_quiz()[universe]
    vec = dict(base)
    for i, q in enumerate(questions):
        letters = [o["letter"] for o in q["options"]] if "letter" in q["options"][0] else None
        if letters is not None:
            continue  # mbti 走字母路径，不聚合 delta
        ans = answers[i] if i < len(answers) else q["options"][0]["label"]
        for opt in q["options"]:
            if opt["label"] == ans:
                for dim, dv in opt["delta"].items():
                    vec[dim] += dv
                break
    return {d: round(min(10.0, max(1.0, vec[d])), 1) for d in DIMS}


def mbti_letters(answers: list[str]) -> str:
    """麦门16型：4 道字母题 → 四字母代号。无效答案回落到每题第一个选项。"""
    questions = load_quiz()["mbti"]
    letters = ""
    for i, q in enumerate(questions):
        ans = answers[i].strip().upper() if i < len(answers) else ""
        chosen = next((o for o in q["options"] if o["label"] == ans), q["options"][0])
        letters += chosen["letter"]
    return letters


def quiz_summary(universe: str, questions: list[dict], answers: list[str]) -> str:
    lines = []
    for i, q in enumerate(questions):
        ans = answers[i].strip().upper() if i < len(answers) else ""
        opt = next((o for o in q["options"] if o["label"] == ans), q["options"][0])
        lines.append(f"Q{i + 1}. {q['text']}")
        lines.append(f"   → {opt['text']}")
    return "\n".join(lines)
