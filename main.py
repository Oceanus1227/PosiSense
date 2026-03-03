import json
from datetime import datetime

from layers.global_sentiment import get_global_sentiment
from layers.global_sectors   import get_global_sectors
from layers.ashare_sentiment import get_ashare_sentiment
from layers.ashare_sectors   import get_ashare_sectors
from engine.position_engine  import calc_position


def run() -> int:
    """
    运行完整仓位评估流程
    返回建议仓位（int，0–100）
    """
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

    # ── 输出结果 ──────────────────────────────────────
    pos   = result["position"]
    score = result["composite_score"]

    # 仓位等级标签
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

    # 各层得分可视化
    print("  各层得分：")
    for layer, s in result["layer_scores"].items():
        filled = int((s + 1.0) * 5)        # 0–10 格
        bar    = "█" * filled + "░" * (10 - filled)
        print(f"    {layer:6s}  [{bar}]  {s:+.3f}")

    print(f"{'─'*48}")

    # 明细
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

    print(f"{'='*48}\n")

    return pos


if __name__ == "__main__":
    position = run()
    # 最终仓位单独打印，方便外部脚本 grep
    print(f"POSITION={position}")
