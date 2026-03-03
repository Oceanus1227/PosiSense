import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def calc_position(
    global_sentiment: dict,
    global_sectors:   dict,
    ashare_sentiment: dict,
    ashare_sectors:   dict,
) -> dict:
    """
    四层加权评分 → 建议仓位
    返回：
        position        : int，建议仓位 %（0–100，step=10）
        composite_score : float，综合得分
        layer_scores    : dict，各层得分明细
        vix_override    : bool，是否触发 VIX 熔断
    """
    w = cfg["weights"]

    # ── 加权综合得分 ──────────────────────────────────
    composite = (
        global_sentiment["score"] * w["global_sentiment"] +
        global_sectors["score"]   * w["global_sectors"]   +
        ashare_sentiment["score"] * w["ashare_sentiment"] +
        ashare_sectors["score"]   * w["ashare_sectors"]
    )
    composite = round(composite, 3)

    # ── 映射到 0–100 ──────────────────────────────────
    # composite = -1.0 → 0%，composite = +1.0 → 100%
    raw_position = (composite + 1.0) / 2.0 * 100.0
    step     = cfg["position"]["step"]
    position = round(raw_position / step) * step
    position = max(cfg["position"]["min"], min(cfg["position"]["max"], position))

    # ── VIX 硬性熔断（优先级最高）────────────────────
    vix_override = False
    vix_val = global_sentiment["detail"].get("VIX")
    if isinstance(vix_val, (int, float)):
        if vix_val >= cfg["vix"]["danger"]:
            position     = 0
            vix_override = True
        elif vix_val >= cfg["vix"]["caution"] and position > 30:
            position     = 30
            vix_override = True

    return {
        "position":        int(position),
        "composite_score": composite,
        "vix_override":    vix_override,
        "layer_scores": {
            "全球情绪": global_sentiment["score"],
            "全球行业": global_sectors["score"],
            "A股情绪":  ashare_sentiment["score"],
            "A股行业":  ashare_sectors["score"],
        },
    }
