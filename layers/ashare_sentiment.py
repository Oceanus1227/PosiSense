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
    """
    返回最近一个交易日（排除周六、周日），格式 YYYYMMDD。
    周一 → 上周五（-3天）
    周六 → 上周五（-1天）
    周日 → 上周五（-2天）
    其余工作日 → 昨天（-1天）
    """
    today = datetime.now()
    wd = today.weekday()   # 0=周一 … 6=周日
    if wd == 0:
        offset = 3   # 周一取上周五
    elif wd == 5:
        offset = 1   # 周六取周五
    elif wd == 6:
        offset = 2   # 周日取周五
    else:
        offset = 1   # 工作日取昨天
    return (today - timedelta(days=offset)).strftime("%Y%m%d")


def _index_score(chg: float) -> float:
    return float(np.interp(chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30,  -0.15,   0.00,  0.00,  0.15,  0.30]))


def _zt_score(zt: int, dt: int) -> float:
    total = zt + dt + 1
    ratio = zt / total
    return float(np.interp(ratio,
        [0.15, 0.30, 0.45, 0.55, 0.70, 0.85],
        [-0.20, -0.10, 0.00, 0.00, 0.10, 0.20]))


def get_ashare_sentiment() -> dict:
    score  = 0.0
    detail = {}

    # ── 上证指数（权重 × 1.5）──
    try:
        df  = ak.stock_zh_index_daily(symbol="sh000001")
        df  = df.sort_values("date").tail(2).reset_index(drop=True)
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        detail["上证涨跌"] = f"{chg * 100:.2f}%"
        detail["上证日期"] = str(df["date"].iloc[-1])
        s = _index_score(chg) * 1.5
        score += s
        detail["上证得分"] = round(s, 3)
    except Exception as e:
        detail["上证涨跌"] = f"获取失败: {e}"

    # ── 深证指数（权重 × 0.5）──
    try:
        df  = ak.stock_zh_index_daily(symbol="sz399001")
        df  = df.sort_values("date").tail(2).reset_index(drop=True)
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        detail["深证涨跌"] = f"{chg * 100:.2f}%"
        s = _index_score(chg) * 0.5
        score += s
        detail["深证得分"] = round(s, 3)
    except Exception as e:
        detail["深证涨跌"] = f"获取失败: {e}"

    # ── 涨停/跌停比 ──
    try:
        trade_date = _latest_trading_date()
        df_zt = ak.stock_zt_pool_em(date=trade_date)
        df_dt = ak.stock_zt_pool_dtgc_em(date=trade_date)
        zt_count = len(df_zt)
        dt_count = len(df_dt)          # ← 修复原来的 dt_coun 拼写错误
        detail["涨停数"] = zt_count
        detail["跌停数"] = dt_count
        detail["涨停日期"] = trade_date
        s = _zt_score(zt_count, dt_count)
        score += s
        detail["涨跌停得分"] = round(s, 3)
    except Exception as e:
        detail["涨停数"] = f"获取失败: {e}"

    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
