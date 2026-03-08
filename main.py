import json
from datetime import datetime
from pathlib import Path

from layers.global_sentiment import get_global_sentiment
from layers.global_sectors   import get_global_sectors
from layers.ashare_sentiment import get_ashare_sentiment
from layers.ashare_sectors   import get_ashare_sectors
from engine.position_engine  import calc_position


# ── 历史记录路径 ──────────────────────────────────
HISTORY_FILE = Path(__file__).parent / "posisense_history.jsonl"


def _save_history(now: str, result: dict, gs: dict, gsc: dict, ash: dict, asc: dict):
    """追加写入一条历史记录"""
    record = {
        "datetime":     now,
        "position":     result["position"],
        "score":        result["composite_score"],
        "vix_override": result["vix_override"],
        "layer_scores": result["layer_scores"],
        "detail": {
            "global_sentiment": gs["detail"],
            "global_strong":    gsc["strong"],
            "global_weak":      gsc["weak"],
            "ashare_sentiment": ash["detail"],
            "ashare_strong":    asc["strong"],
            "ashare_weak":      asc["weak"],
        },
    }
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"  💾 历史记录已追加 → {HISTORY_FILE.name}（共 {_count_history()} 条）")


def _count_history() -> int:
    if not HISTORY_FILE.exists():
        return 0
    with HISTORY_FILE.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def run() -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*48}")
    print(f"  📊 PosiSense  |  {now}")
    print(f"{'='*48}")

    print("🌐 [1/4] 获取全球宏观情绪...")
    gs = get_global_sentiment()

    print("🏭 [2/4] 获取全球行业走势...")
    gsc = get_global_sectors()

    print("🇨🇳 [3/4] 获取A股市场情绪...")
    ash = get_ashare_sentiment()

    print("📈 [4/4] 获取A股行业走势...")
    asc = get_ashare_sectors()

    print("\n🧮 计算仓位中...\n")
    result = calc_position(gs, gsc, ash, asc)

    pos   = result["position"]
    score = result["composite_score"]

    if pos >= 80:
        label = "🟢 积极进攻"
    elif pos >= 60:
        label = "🟡 标准持仓"
    elif pos >= 40:
        label = "🟠 谨慎持仓"
    elif pos >= 20:
        label = "🔴 轻仓防守"
    else:
        label = "⚫ 空仓观望"

    print(f"{'─'*48}")
    print(f"  建议仓位：{pos}%   {label}")
    if result["vix_override"]:
        print(f"  ⚠️  VIX 熔断已触发，仓位已强制调整")
    print(f"  综合得分：{score:+.3f}")
    print(f"{'─'*48}")

    print("  各层得分：")
    for layer, s in result["layer_scores"].items():
        filled = int((s + 1.0) * 5)
        bar    = "█" * filled + "░" * (10 - filled)
        print(f"    {layer:6s}  [{bar}]  {s:+.3f}")

    print(f"{'─'*48}")

    print("  全球情绪明细：")
    for k, v in gs["detail"].items():
        print(f"    {k}: {v}")

    print(f"\n  全球强势行业：{gsc['strong'] or '无'}")
    print(f"  全球弱势行业：{gsc['weak']   or '无'}")

    print(f"\n  A股情绪明细：")
    for k, v in ash["detail"].items():
        print(f"    {k}: {v}")

    print(f"\n  A股强势行业：{asc['strong'] or '无'}")
    print(f"  A股弱势行业：{asc['weak']   or '无'}")

    print(f"{'─'*48}")

    # ── 保存历史记录 ──────────────────────────────
    _save_history(now, result, gs, gsc, ash, asc)

    print(f"{'='*48}\n")
    return pos


if __name__ == "__main__":
    position = run()
    print(f"POSITION={position}")
