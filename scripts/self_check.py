#!/usr/bin/env python3
"""麦门平行宇宙 · 发布前一键自检（考察验收工具）。

用法:
    python scripts/self_check.py             # 完整自检（离线，约 1 分钟）
    python scripts/self_check.py --quick     # 只查文件/密钥/合规，不跑测试和命令
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok, detail))
    print(f"  {'✅' if ok else '❌'} {name}" + (f" —— {detail}" if detail else ""))
    return ok


print("=" * 66)
print("🍔 麦门平行宇宙 · 发布前自检")
print("=" * 66)

# ---------- ① 比赛必备文件 ----------
print("\n① 比赛必备文件（活动规则要求的标准命名）")
REQUIRED = [
    "README.md", "CONTEST_DECLARATION.md", "MCP_INTEGRATION.md",
    "mcp-config.example.json", "workbuddy.md", "SKILL.md", "GUIDE.md",
    "demo.py", "LICENSE", "mcparallel/cli.py", "data/personas.json", "tests/test_mcparallel.py",
]
missing = [f for f in REQUIRED if not os.path.exists(f)]
check("必备文件齐全", not missing, f"缺失: {missing}" if missing else f"{len(REQUIRED)} 个全部就位")

decl = open("CONTEST_DECLARATION.md", encoding="utf-8").read() if os.path.exists("CONTEST_DECLARATION.md") else ""
check("参赛声明为官方模板（五段结构完整）",
      all(k in decl for k in ("原创性声明", "合规声明", "信息安全声明", "规则遵守声明")),
      "含原创性/合规/信息安全/使用提示/规则遵守五节" if "原创性声明" in decl else "内容异常，需重新下载官方模板")

# ---------- ② 密钥与隐私 ----------
print("\n② 密钥与隐私（零泄漏）")
token = None
if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        if line.startswith("MCD_MCP_TOKEN="):
            token = line.split("=", 1)[1].strip()
cfg = open("mcp-config.example.json", encoding="utf-8").read()
check("mcp-config.example.json 仅含环境变量占位符",
      "${MCD_MCP_TOKEN}" in cfg and (not token or token not in cfg))

leaks = []
if token:
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in (".git", "docs", "__pycache__", ".venv")]
        for f in files:
            if f == ".env":
                continue
            p = os.path.join(root, f)
            try:
                if token in open(p, encoding="utf-8").read():
                    leaks.append(p)
            except (UnicodeDecodeError, PermissionError):
                pass
check("真实 Token 不出现在任何待提交文件", not leaks, f"泄漏: {leaks}" if leaks else "全仓库扫描通过")

ignored = subprocess.run(["git", "check-ignore", ".env", "docs/probe/", "docs/internal/"],
                         capture_output=True, text=True).stdout.split()
check(".env / docs/probe / docs/internal 均被 gitignore", len(ignored) >= 2, f"已忽略 {len(ignored)} 项")

# ---------- ③ 内容合规（公开文件硬扫描） ----------
print("\n③ 内容合规（公开文件不得出现竞品品牌/真人名/游戏角色名）")
sys.path.insert(0, ROOT)
from mcparallel.llm_copy import COMPETITOR_BRANDS, GAME_CHARACTERS, REAL_PEOPLE  # noqa: E402

PUBLIC_FILES = [
    "README.md", "GUIDE.md", "SKILL.md", "workbuddy.md", "MCP_INTEGRATION.md",
    "data/personas.json", "data/quiz.json", "mcparallel/llm_copy.py",  # llm_copy 是黑名单本体，单独放行
]
public_targets = [f for f in PUBLIC_FILES if f != "mcparallel/llm_copy.py" and os.path.exists(f)]
hard_hits = []
for f in public_targets:
    text = open(f, encoding="utf-8").read()
    for word in COMPETITOR_BRANDS + REAL_PEOPLE + GAME_CHARACTERS:
        if word.strip() and word in text:
            hard_hits.append(f"{f}: {word}")
check("公开文件零违禁词", not hard_hits, f"命中: {hard_hits[:5]}" if hard_hits else "竞品/真人/角色名扫描通过")
check("内部策划文档未入库", not os.path.exists("docs/competitor-analysis.md"))

if "--quick" in sys.argv:
    print("\n" + "=" * 66)
    fails = [r for r in RESULTS if not r[1]]
    print(f"快速自检完成: {len(RESULTS) - len(fails)}/{len(RESULTS)} 通过")
    sys.exit(1 if fails else 0)

# ---------- ④ 单元测试 ----------
print("\n④ 单元测试")
r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                   capture_output=True, text=True)
m = re.search(r"Ran (\d+) tests.*\n\nOK", r.stderr)
check("测试套件全绿", bool(m), m.group(0).strip().replace("\n", " ") if m else r.stderr[-200:])

# ---------- ⑤ 全命令回归（离线零 Token） ----------
print("\n⑤ CLI 全命令回归（离线模式）")
COMMANDS = [
    ["draw", "--seed", "3"], ["draw", "--persona", "峡谷刺客型", "--seed", "3"],
    ["quiz", "--universe", "game", "--answers", "A,B,C"],
    ["quiz", "--universe", "mbti", "--answers", "A,B,A,B"],
    ["forward", "--persona", "摸鱼艺术家型"],
    ["reverse", "--items", "巨无霸,麦乐鸡,可乐"],
    ["guide", "--budget", "25"], ["guide", "--goal", "fitness"], ["guide"],
    ["card", "--universe", "game", "--answers", "A,A,A"], ["lottery"],
]
failed_cmds = []
for cmd in COMMANDS:
    rr = subprocess.run([sys.executable, "-m", "mcparallel", *cmd], capture_output=True, text=True,
                        stdin=subprocess.DEVNULL)
    if rr.returncode != 0:
        failed_cmds.append(" ".join(cmd))
check("全部 CLI 命令通过", not failed_cmds, f"失败: {failed_cmds}" if failed_cmds else f"{len(COMMANDS)} 条命令 OK")

# 无 TTY 环境不崩溃（Bug 1 修复回归）
r = subprocess.run([sys.executable, "-m", "mcparallel", "quiz", "--universe", "game"],
                   capture_output=True, text=True, stdin=subprocess.DEVNULL)
check("无 TTY 环境交互式 quiz 不崩溃", r.returncode == 0 and "--answers" in r.stdout)

# ---------- ⑥ Demo 与产物卫生 ----------
print("\n⑥ Demo 与产物卫生")
r = subprocess.run([sys.executable, "demo.py"], capture_output=True, text=True)
check("demo.py 跑通", r.returncode == 0)
cards = set(os.listdir("output/cards")) if os.path.isdir("output/cards") else set()
expected_cards = {"sample-card.svg", "sample-card-worker.svg", "demo-card.svg"}
check("身份卡目录无时间戳垃圾", cards <= expected_cards, f"当前: {sorted(cards)}")

# ---------- 汇总 ----------
print("\n" + "=" * 66)
fails = [r for r in RESULTS if not r[1]]
if fails:
    print(f"❌ 自检未通过: {len(fails)} 项失败 —— " + "; ".join(f[0] for f in fails))
    sys.exit(1)
print(f"✅ 自检全部通过（{len(RESULTS)}/{len(RESULTS)}）—— 仓库处于可发布状态")
print("   发布三步：① 建公开仓库并 push  ② 替换 skills/mcparallel/SKILL.md 中的仓库占位链接")
print("   ③ 在官方仓库发 Issue：【参赛申请】麦门平行宇宙（名称/地址/简介三行，链接用纯文本）")
