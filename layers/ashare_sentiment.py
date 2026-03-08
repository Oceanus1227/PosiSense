import numpy as np
import akshare as ak
import pandas as pd
import yaml
import os
from datetime import datetime, timedelta

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _latest_trading_date() -> str:
    """返回最近一个交易日（排除周末），格式 YYYYMMDD"""
    today = datetime.now()
    offset = 1
    if today.weekday() == 0:   # 周一 → 取上周五
        offset = 3
    elif today.weekday() == 6: # 周日 → 取上周五
        offset = 2
    return (today - timedelta(days=offset)).strftime("%Y%m%d")


def _index_score(chg: float) -> float:
    """指数涨跌幅（小数）→ 得分，连续映射"""
    return float(np.interp(chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30]))


def _north_score(flow: float) -> float:
    """
    北向资金净买额（亿元）→ 得分，连续映射
    -100亿 → -0.30 | 0 → 0.00 | +100亿 → +0.30
    """
    return float(np.interp(flow,
        [-100, -50,  -10,  10,   50,  100],
        [-0.30, -0.15, 0.00, 0.00, 0.15, 0.30]))


def _zt_score(zt: int, dt: int) -> float:
    """
    涨停/跌停比 → 得分，连续映射
    ratio = zt / (zt + dt + 1)，范围 0~1，映射到 -0.20 ~ +0.20
    """
    total = zt + dt + 1  # +1 防止除零
    ratio = zt / total
    # ratio 0.2 → -0.20 | 0.5 → 0.00 | 0.8 → +0.20
    return float(np.interp(ratio,
        [0.15, 0.30, 0.45, 0.55, 0.70, 0.85],
        [-0.20, -0.10, 0.00, 0.00, 0.10, 0.20]))


def get_ashare_sentiment() -> dict:
    """
    A股市场情绪评分
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细
    """
    score = 0.0
    detail = {}

    # ── 上证指数（连续映射）───────────────────────
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df = df.sort_values("date").tail(2).reset_index(drop=True)
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        detail["上证涨跌"] = f"{chg * 100:.2f}%"
        detail["上证日期"] = str(df["date"].iloc[-1])
        s = _index_score(chg) * 1.5  # 上证权重更高
        score += s
        detail["上证得分"] = round(s, 3)
    except Exception as e:
        detail["上证涨跌"] = f"获取失败: {e}"

    # ── 深证指数（连续映射）───────────────────────
    try:
        df = ak.stock_zh_index_daily(symbol="sz399001")
        df = df.sort_values("date").tail(2).reset_index(drop=True)
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        detail["深证涨跌"] = f"{chg * 100:.2f}%"
        s = _index_score(chg) * 0.5  # 深证权重较低
        score += s
        detail["深证得分"] = round(s, 3)
    except Exception as e:
        detail["深证涨跌"] = f"获取失败: {e}"

    # ── 北向资金（连续映射）───────────────────────
    try:
        df_north = ak.stock_hsgt_hist_em(symbol="北向资金")
        df_north = df_north.sort_values("日期").tail(1)
        flow = float(df_north["当日成交净买额"].iloc[-1])
        detail["北向资金(亿)"] = round(flow, 2)
        detail["北向日期"] = str(df_north["日期"].iloc[-1])
        s = _north_score(flow)
        score += s
        detail["北向得分"] = round(s, 3)
    except Exception as e:
        detail["北向资金"] = f"获取失败: {e}"

    # ── 涨停/跌停比（新增）────────────────────────
    try:
        df_zt = ak.stock_zt_pool_em(date=_latest_trading_date())
        df_dt = ak.stock_zt_pool_dtgc_em(date=_latest_trading_date())
        zt_count = len(df_zt)
        dt_count = len(df_dt)
        detail["涨停数"] = zt_count
        detail["跌停数"] = dt_count
        s = _zt_score(zt_count, dt_count)
        score += s
        detail["涨跌停得分"] = round(s, 3)
    except Exception as e:
        detail["涨跌停"] = f"获取失败: {e}"

    # ── 归一化 ────────────────────────────────────
    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
