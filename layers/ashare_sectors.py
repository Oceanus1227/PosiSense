"""
A股市场情绪层
数据源：akshare
  - 上证 / 深证 / 创业板 指数涨跌幅
  - 涨停 / 跌停家数
  - 市场成交量变化
"""

import numpy as np
import akshare as ak
import pandas as pd
import yaml
import os
from datetime import datetime, timedelta

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


# ── 工具函数 ─────────────────────────────────────────

def _latest_trading_date() -> str:
    """返回最近一个交易日（排除周末），格式 YYYYMMDD"""
    today = datetime.now()
    offset = 1
    if today.weekday() == 0:    # 周一 → 取上周五
        offset = 3
    elif today.weekday() == 6:  # 周日 → 取上周五
        offset = 2
    return (today - timedelta(days=offset)).strftime("%Y%m%d")


def _index_score(chg: float) -> float:
    """指数涨跌幅（小数）→ 得分，连续映射"""
    return float(np.interp(
        chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30],
    ))


def _zt_score(zt: int, dt: int) -> float:
    """涨停/跌停比 → 得分，连续映射"""
    total = zt + dt + 1  # +1 防止除零
    ratio = zt / total
    return float(np.interp(
        ratio,
        [0.15, 0.30, 0.45, 0.55, 0.70, 0.85],
        [-0.20, -0.10, 0.00, 0.00, 0.10, 0.20],
    ))


def _volume_score(vol_chg: float) -> float:
    """成交量变化率（小数）→ 得分"""
    return float(np.interp(
        vol_chg,
        [-0.30, -0.10, 0.0, 0.10, 0.30],
        [-0.10, -0.05, 0.00, 0.05, 0.10],
    ))


def _get_index_chg(symbol: str) -> float | None:
    """获取 A 股指数最近一日涨跌幅（小数形式）"""
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        df = df.dropna(subset=["close"])
        if len(df) < 2:
            return None
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        return float(chg)
    except Exception:
        return None


# ── 主函数 ───────────────────────────────────────────

def get_ashare_sentiment() -> dict:
    """
    A股市场情绪评分
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细
    """
    score = 0.0
    detail = {}

    # ── A股三大指数 ───────────────────────────────
    indices = {
        "上证指数": "sh000001",
        "深证成指": "sz399001",
        "创业板指": "sz399006",
    }
    index_changes = []
    for name, symbol in indices.items():
        chg = _get_index_chg(symbol)
        if chg is not None:
            detail[name] = f"{chg * 100:.2f}%"
            index_changes.append(chg)
        else:
            detail[name] = "获取失败"

    if index_changes:
        avg = sum(index_changes) / len(index_changes)
        idx_s = _index_score(avg)
        score += idx_s
        detail["A股均涨跌得分"] = round(idx_s, 3)

    # ── 涨停 / 跌停家数 ──────────────────────────
    try:
        date_str = _latest_trading_date()
        df_zt = ak.stock_zt_pool_em(date=date_str)
        df_dt = ak.stock_zt_pool_dtgc_em(date=date_str)
        zt_count = len(df_zt) if df_zt is not None else 0
        dt_count = len(df_dt) if df_dt is not None else 0
        detail["涨停家数"] = zt_count
        detail["跌停家数"] = dt_count
        zt_s = _zt_score(zt_count, dt_count)
        score += zt_s
        detail["涨跌停得分"] = round(zt_s, 3)
    except Exception as e:
        detail["涨跌停"] = f"获取失败: {e}"

    # ── 市场成交量情绪（上证成交量 5 日均量比）───
    try:
        df_vol = ak.stock_zh_index_daily(symbol="sh000001")
        df_vol = df_vol.dropna(subset=["volume"])
        if len(df_vol) >= 6:
            vol_today = float(df_vol["volume"].iloc[-1])
            vol_ma5   = float(df_vol["volume"].iloc[-6:-1].mean())
            vol_chg   = (vol_today - vol_ma5) / vol_ma5 if vol_ma5 > 0 else 0.0
            detail["成交量变化"] = f"{vol_chg * 100:.1f}%"
            vol_s = _volume_score(vol_chg)
            score += vol_s
            detail["成交量得分"] = round(vol_s, 3)
    except Exception as e:
        detail["成交量"] = f"获取失败: {e}"

    # ── 归一化 ────────────────────────────────────
    score = max(-1.0, min(1.0, round(score, 3)))

    return {"score": score, "detail": detail}
