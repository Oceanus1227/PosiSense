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
    返回最近一个交易日，排除周末。
    如果 akshare 返回空数据，自动往前回退最多 10 天。
    """
    today = datetime.now()
    for offset in range(1, 11):
        dt = today - timedelta(days=offset)
        if dt.weekday() < 5:  # 跳过周末
            date_str = dt.strftime("%Y%m%d")
            try:
                df = ak.stock_zt_pool_em(date=date_str)
                if df is not None and not df.empty:
                    return date_str
            except Exception:
                continue
    # 兜底：返回最近的工作日（可能无数据）
    for offset in range(1, 4):
        dt = today - timedelta(days=offset)
        if dt.weekday() < 5:
            return dt.strftime("%Y%m%d")
    return (today - timedelta(days=1)).strftime("%Y%m%d")


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
        dt_count = len(df_dt)
        detail["涨停数"] = zt_count
        detail["跌停数"] = dt_count
        detail["涨停日期"] = trade_date
        s = _zt_score(zt_count, dt_count)
        score += s
        detail["涨停跌停得分"] = round(s, 3)
    except Exception as e:
        detail["涨停跌停"] = f"获取失败: {e}"

    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
