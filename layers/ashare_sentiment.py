"""
A股市场情绪层
数据源：iFinD（指数涨跌 + 成交量变化）
"""

import numpy as np
import yaml
import os
from datetime import datetime, timedelta

from utils.ifind_client import ifind_history

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _index_score(chg: float) -> float:
    """指数涨跌幅（小数）→ 得分 [-0.30, +0.30]"""
    return float(np.interp(
        chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30],
    ))


def _volume_score(vol_chg: float) -> float:
    """成交量变化率（小数）→ 得分 [-0.10, +0.10]"""
    return float(np.interp(
        vol_chg,
        [-0.30, -0.10, 0.0, 0.10, 0.30],
        [-0.10, -0.05, 0.00, 0.05, 0.10],
    ))


def _recent_dates(days: int = 10) -> tuple[str, str]:
    """返回最近 N 天的起止日期 (start, end)，格式 YYYY-MM-DD"""
    end   = datetime.now()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _get_index_chg_ifind(code: str) -> tuple[float | None, float | None]:
    """
    通过 iFinD 获取指数最近一日涨跌幅 + 成交量变化
    返回 (chg, vol_chg) 或 (None, None)
    """
    try:
        start, end = _recent_dates(10)
        df = ifind_history(code, start, end, indicators="close,volume")
        df = df.dropna(subset=["close"])
        if len(df) < 2:
            return None, None

        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]

        vol_chg = None
        if "volume" in df.columns and len(df) >= 6:
            vol_today = float(df["volume"].iloc[-1])
            vol_ma5   = float(df["volume"].iloc[-6:-1].mean())
            if vol_ma5 > 0:
                vol_chg = (vol_today - vol_ma5) / vol_ma5

        return float(chg), vol_chg
    except Exception:
        return None, None


def get_ashare_sentiment() -> dict:
    """
    A股市场情绪评分（iFinD 数据源）
    返回：score (-1.0 ~ +1.0), detail
    """
    score  = 0.0
    detail = {}

    indices = cfg.get("ashare_indices", {
        "上证指数": "000001.SH",
        "深证成指": "399001.SZ",
        "创业板指": "399006.SZ",
    })

    # ── 三大指数涨跌幅 ───────────────────────────
    index_changes = []
    vol_changes   = []

    for name, code in indices.items():
        chg, vol_chg = _get_index_chg_ifind(code)
        if chg is not None:
            detail[name] = f"{chg * 100:.2f}%"
            index_changes.append(chg)
        else:
            detail[name] = "获取失败"

        if vol_chg is not None:
            vol_changes.append(vol_chg)

    if index_changes:
        avg = sum(index_changes) / len(index_changes)
        idx_s = _index_score(avg)
        score += idx_s
        detail["A股均涨跌得分"] = round(idx_s, 3)

    # ── 成交量情绪（三大指数均量比）───────────────
    if vol_changes:
        avg_vol = sum(vol_changes) / len(vol_changes)
        detail["成交量变化"] = f"{avg_vol * 100:.1f}%"
        vol_s = _volume_score(avg_vol)
        score += vol_s
        detail["成交量得分"] = round(vol_s, 3)

    # ── 归一化 ────────────────────────────────────
    score = max(-1.0, min(1.0, round(score, 3)))

    return {"score": score, "detail": detail}
