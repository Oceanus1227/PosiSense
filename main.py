import json
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from layers.global_sentiment import get_global_sentiment
from layers.global_sectors   import get_global_sectors
from layers.ashare_sentiment import get_ashare_sentiment
from layers.ashare_sectors   import get_ashare_sectors
from engine.position_engine  import calc_position
from notifier.feishu         import send_feishu

HISTORY_FILE = Path(__file__).parent / "posisense_history.jsonl"


def _save_history(now: str, result: dict, gs: dict, gsc: dict, ash: dict, asc: dict):
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
            "ashare_rank":      asc.get("rank", []),
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


def _fetch_all() -> dict:
    """四层数据并发获取"""
    tasks = {
        "gs":  get_global_sentiment,
        "gsc": get_global_sectors,
        "ash": get_ashare_sentiment,
        "asc": get_ashare_sectors,
    }
    labels = {
        "gs":  "🌐 全球宏观情绪",
        "gsc": "🏭 全球行业走势",
        "ash": "🇨🇳 A股市场情绪",
        "asc": "📈 A股行业走势",
    }
    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_key = {executor.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(future_to_key):
            key = future_to_key[future]
            try:
                results[key] = future.result()
                print(f"  ✅ {labels[key]} 获取完成")
            except Exception as e:
                print(f"  ❌ {labels[key]} 获取失败: {e}")
                results[key] = {"score": 0.0, "detail": {}, "strong": [], "weak": [], "rank": []}
    return results


def _print_sector_rank(rank: list, top_n: int = 5):
    """打印行业涨跌幅排行：前N、省略号、后N"""
    total = len(rank)
    if total == 0:
        print("    （暂无数据）")
        return

    def _print_row(item):
        chg     = item["chg"]
        bar_len = int((chg + 5) / 10 * 10)
        bar_len = max(0, min(10, bar_len))
        bar     = "█" * bar_len + "░" * (10 - bar_len)
        print(f"    {item['rank']:>3}. {item['name']:<10} [{bar}] {chg:+.2f}%")

    top    = rank[:top_n]
    bottom = rank[-top_n:]

    for item in top:
        _print_row(item)

    if total > top_n * 2:
        print(f"    {'···':^28}（共 {total} 个行业）")
    elif total > top_n:
        print(f"    {'···':^28}")

    for item in bottom:
        _print_row(item)


def run() -> int:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*48}")
    print(f"  📊 PosiSense  |  {now}")
    print(f"{'='*48}")
    print("⚡ 并发获取四层数据中...\n")

    data = _fetch_all()
    gs  = data["gs"]
    gsc = data["gsc"]
    ash = data["ash"]
    asc = data["asc"]

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

    # ── 各层得分 ──────────────────────────────────
    print("  各层得分：")
    for layer, s in result["layer_scores"].items():
        filled = int((s + 1.0) * 5)
        bar    = "█" * filled + "░" * (10 - filled)
        print(f"    {layer:6s}  [{bar}]  {s:+.3f}")
    print(f"{'─'*48}")

    # ── 全球情绪明细 ──────────────────────────────
    print("  全球情绪明细：")
    for k, v in gs["detail"].items():
        print(f"    {k}: {v}")

    print(f"\n  全球强势行业：{', '.join(gsc['strong']) if gsc['strong'] else '无'}")
    print(f"  全球弱势行业：{', '.join(gsc['weak'])   if gsc['weak']   else '无'}")

    # ── A股情绪明细 ───────────────────────────────
    print(f"\n  A股情绪明细：")
    for k, v in ash["detail"].items():
        print(f"    {k}: {v}")

    # ── A股行业涨跌幅排行 ─────────────────────────
    asc_detail = asc.get("detail", {})
    if "错误" in asc_detail:
        print(f"\n  ⚠️  A股行业数据异常: {asc_detail['错误']}")
        if "_columns" in asc_detail:
            print(f"  实际列名: {asc_detail['_columns']}")

    print(f"\n  A股行业涨跌幅排行（前5 / 后5）：")
    _print_sector_rank(asc.get("rank", []), top_n=5)

    print(f"\n  A股强势行业：{', '.join(asc['strong']) if asc['strong'] else '无'}")
    print(f"  A股弱势行业：{', '.join(asc['weak'])   if asc['weak']   else '无'}")

    print(f"{'─'*48}")

    # ── 保存历史 & 飞书推送 ───────────────────────
    _save_history(now, result, gs, gsc, ash, asc)
    send_feishu(result, gs, gsc, ash, asc)          # ← 新增

    print(f"{'='*48}\n")

    return pos


if __name__ == "__main__":
    position = run()
    print(f"POSITION={position}")
