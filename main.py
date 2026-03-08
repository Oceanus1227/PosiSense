"""
PosiSense 主入口
并行采集四层数据 → 计算仓位 → 输出 → 存历史 → 飞书推送
"""

import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml

from layers.global_sentiment import get_global_sentiment
from layers.global_sectors   import get_global_sectors
from layers.ashare_sentiment import get_ashare_sentiment
from layers.ashare_sectors   import get_ashare_sectors
from engine.position_engine  import calc_position
from notifier.feishu         import send_feishu

_cfg_path = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _save_history(result: dict, gs: dict, gsc: dict, ash: dict, asc: dict):
    """追加 JSONL 历史记录"""
    hist_cfg = cfg.get("history", {})
    if not hist_cfg.get("enabled", False):
        return

    path = hist_cfg.get("path", "history.jsonl")
    record = {
        "timestamp":       datetime.now().isoformat(),
        "position":        result["position"],
        "composite_score": result["composite_score"],
        "vix_override":    result["vix_override"],
        "layer_scores":    result["layer_scores"],
        "global_sentiment": gs["detail"],
        "global_sectors":   gsc["detail"],
        "ashare_sentiment": ash["detail"],
        "ashare_sectors_strong": asc["strong"],
        "ashare_sectors_weak":   asc["weak"],
    }
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"💾 历史记录已保存 → {path}")
    except Exception as e:
        print(f"⚠️  历史记录保存失败: {e}")


def run() -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*48}")
    print(f"  📊 PosiSense  |  {now}")
    print(f"{'='*48}")

    # ── 并行采集 ──────────────────────────────────
    tasks = {
        "global_sentiment": get_global_sentiment,
        "global_sectors":   get_global_sectors,
        "ashare_sentiment": get_ashare_sentiment,
        "ashare_sectors":   get_ashare_sectors,
    }
    labels = {
        "global_sentiment": "🌐 全球宏观情绪",
        "global_sectors":   "🏭 全球行业走势",
        "ashare_sentiment": "🇨🇳 A股市场情绪",
        "ashare_sectors":   "📈 A股行业走势",
    }
    results = {}

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {executor.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(future_map):
            key = future_map[future]
            try:
                results[key] = future.result()
                s = results[key]["score"]
                print(f"  ✅ {labels[key]}  score={s:+.3f}")
            except Exception as e:
                print(f"  ❌ {labels[key]}  失败: {e}")
                results[key] = {
                    "score": 0.0, "detail": {"错误": str(e)},
                    "strong": [], "weak": [],
                }

    gs  = results["global_sentiment"]
    gsc = results["global_sectors"]
    ash = results["ashare_sentiment"]
    asc = results["ashare_sectors"]

    # ── 计算仓位 ──────────────────────────────────
    print("\n🧮 计算仓位中...\n")
    result = calc_position(gs, gsc, ash, asc)

    pos   = result["position"]
    score = result["composite_score"]

    if pos >= 80:   label = "🟢 积极进攻"
    elif pos >= 60: label = "🟡 标准持仓"
    elif pos >= 40: label = "🟠 谨慎持仓"
    elif pos >= 20: label = "🔴 轻仓防守"
    else:           label = "⚫ 空仓观望"

    # ── 控制台输出 ────────────────────────────────
    print(f"{'─'*48}")
    print(f"  建议仓位：{pos}%   {label}")
    if result["vix_override"]:
        print(f"  ⚠️  VIX 熔断已触发，仓位已强制调整")
    print(f"  综合得分：{score:+.3f}")
    print(f"{'─'*48}")

    print("  各层得分：")
    for layer, s in result["layer_scores"].items():
        filled = max(0, min(10, int((s + 1.0) * 5)))
        bar    = "█" * filled + "░" * (10 - filled)
        print(f"    {layer:6s}  [{bar}]  {s:+.3f}")
    print(f"{'─'*48}")

    # ── 保存 & 推送 ──────────────────────────────
    _save_history(result, gs, gsc, ash, asc)
    send_feishu(result, gs, gsc, ash, asc)

    return pos


if __name__ == "__main__":
    run()
