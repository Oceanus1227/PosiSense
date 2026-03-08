"""
A股行业板块强弱评分
数据源：iFinD（同花顺行业指数）
"""

import yaml
import os
from datetime import datetime, timedelta

from utils.ifind_client import ifind_history

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _recent_dates(days: int = 10) -> tuple[str, str]:
    end   = datetime.now()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _get_sector_chg(code: str) -> float | None:
    """通过 iFinD 获取行业指数最近一日涨跌幅"""
    try:
        start, end = _recent_dates(10)
        df = ifind_history(code, start, end, indicators="close")
        df = df.dropna(subset=["close"])
        if len(df) < 2:
            return None
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        return float(chg)
    except Exception:
        return None


def get_ashare_sectors() -> dict:
    """
    A股行业走势评分（iFinD 数据源）
    返回：score, strong, weak, detail
    """
    sector_codes = cfg.get("ashare_sector_codes", {})
    strong_thr   = cfg["ashare_sector"]["strong_threshold"] / 100  # config 里是百分比，转小数
    weak_thr     = cfg["ashare_sector"]["weak_threshold"] / 100
    top_n        = cfg["ashare_sector"]["top_n"]

    strong, weak = [], []
    detail = {}

    for name, code in sector_codes.items():
        chg = _get_sector_chg(code)
        if chg is not None:
            detail[name] = f"{chg * 100:.2f}%"
            if chg > strong_thr:
                strong.append(name)
            elif chg < weak_thr:
                weak.append(name)
        else:
            detail[name] = "获取失败"

    # 按涨跌幅排序
    sorted_sectors = sorted(
        [(k, v) for k, v in detail.items() if v != "获取失败"],
        key=lambda x: float(x[1].replace("%", "")),
        reverse=True,
    )
    detail = {k: v for k, v in sorted_sectors}

    total = len(sector_codes)
    net   = (len(strong) - len(weak)) / total if total > 0 else 0.0
    score = max(-1.0, min(1.0, round(net, 3)))

    return {
        "score":  score,
        "strong": strong[:top_n],
        "weak":   weak[:top_n],
        "detail": detail,
    }
