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
    elif today.weekday() == 6:  # 周日 → 取上周五
        offset = 2
    return (today - timedelta(days=offset)).strftime("%Y%m%d")


def get_ashare_sentiment() -> dict:
    """
    A股市场情绪评分
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细
    """
    score  = 0.0
    detail = {}
    last_date = _latest_trading_date()

    # ── 上证指数涨跌 ──────────────────────────────────
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df = df.sort_values("date").tail(2).reset_index(drop=True)
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        detail["上证涨跌"] = f"{chg * 100:.2f}%"
        detail["上证日期"] = str(df["date"].iloc[-1])
        if chg > 0.010:
            score += 0.30
        elif chg > 0.003:
            score += 0.15
        elif chg > -0.003:
            score += 0.00
        elif chg > -0.010:
            score -= 0.15
        else:
            score -= 0.30
    except Exception as e:
        detail["上证涨跌"] = f"获取失败: {e}"

    # ── 深证指数涨跌 ──────────────────────────────────
    try:
        df = ak.stock_zh_index_daily(symbol="sz399001")
        df = df.sort_values("date").tail(2).reset_index(drop=True)
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        detail["深证涨跌"] = f"{chg * 100:.2f}%"
        if chg > 0.010:
            score += 0.10
        elif chg > 0:
            score += 0.05
        elif chg > -0.010:
            score -= 0.05
        else:
            score -= 0.10
    except Exception as e:
        detail["深证涨跌"] = f"获取失败: {e}"


    # ── 北向资金 ──────────────────────────────────────
    try:
        df_north = ak.stock_hsgt_hist_em(symbol="北向资金")
        df_north = df_north.sort_values("日期").tail(1)
        flow = float(df_north["当日成交净买额"].iloc[-1])  # 单位：亿元
        detail["北向资金(亿)"] = round(flow, 2)
        detail["北向日期"]     = str(df_north["日期"].iloc[-1])
        if flow > 50:
            score += 0.30
        elif flow > 10:
            score += 0.15
        elif flow > -10:
            score += 0.00
        elif flow > -50:
            score -= 0.15
        else:
            score -= 0.30
    except Exception as e:
        detail["北向资金"] = f"获取失败: {e}"


    # ── 涨跌停比 ──────────────────────────────────────
    try:
        df_limit = ak.stock_zt_pool_em(date=last_date)
        up_count = len(df_limit)

        df_dt = ak.stock_zt_pool_em(date=last_date)
        down_count = len(df_dt)

        detail["涨停数"] = up_count
        detail["跌停数"] = down_count
        ratio = up_count / (down_count + 1)
        if ratio > 3.0:
            score += 0.20
        elif ratio > 1.5:
            score += 0.10
        elif ratio < 0.5:
            score -= 0.20
        else:
            score -= 0.05
    except Exception as e:
        detail["涨跌停比"] = f"获取失败: {e}"

    # ── 成交量（与5日均量对比）────────────────────────
    try:
        df_vol = ak.stock_zh_index_daily(symbol="sh000001")
        df_vol = df_vol.sort_values("date").tail(6).reset_index(drop=True)
        avg5      = df_vol["volume"].iloc[:-1].mean()
        today_vol = df_vol["volume"].iloc[-1]
        vol_ratio = today_vol / avg5 if avg5 > 0 else 1.0
        detail["量比(vs5日均)"] = round(vol_ratio, 2)
        if vol_ratio > 1.3:
            score += 0.20
        elif vol_ratio > 0.8:
            score += 0.00
        else:
            score -= 0.20
    except Exception as e:
        detail["量比"] = f"获取失败: {e}"

    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
