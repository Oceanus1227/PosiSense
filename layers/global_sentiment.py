import numpy as np
import pandas as pd
import yfinance as yf
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _index_score(chg: float) -> float:
    return float(np.interp(chg,
        [-0.03, -0.015, -0.003, 0.003, 0.015, 0.03],
        [-1.00,  -0.50,   0.00,  0.00,  0.50,  1.00]))


def _vix_score(vix: float) -> float:
    return float(np.interp(vix,
        [10,   15,   20,    25,    30,    40,    50],
        [1.00, 0.50, 0.00, -0.50, -0.80, -1.00, -1.00]))


def _fetch_close(ticker: str, period: str = "15d",
                 auto_adjust: bool = True) -> pd.Series:
    df = yf.download(ticker, period=period, interval="1d",
                     progress=False, auto_adjust=auto_adjust)
    if df.empty:
        raise ValueError(f"{ticker} 返回空数据")

    # 兼容新版 yfinance MultiIndex 列结构
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    if "Close" not in df.columns:
        raise ValueError(f"{ticker} 无 Close 列，实际列: {list(df.columns)}")

    close = df["Close"].dropna()
    close.index = pd.to_datetime(close.index)
    close = close.sort_index()

    if len(close) == 0:
        raise ValueError(f"{ticker} 清洗后无有效数据")
    return close


def _safe_chg(close: pd.Series, ticker: str = "") -> float | None:
    if len(close) < 2:
        print(f"  [WARN] {ticker} 数据不足 2 条，跳过")
        return None
    prev = float(close.iloc[-2])
    last = float(close.iloc[-1])
    if prev == 0:
        return None
    return (last - prev) / prev


def get_global_sentiment() -> dict:
    """
    全球宏观情绪评分
    数据来源：VIX（40%）+ 标普500（40%）+ 纳斯达克（20%）
    """
    score  = 0.0
    detail = {}

    # ── VIX（权重 40%）—— 必须 auto_adjust=False ──
    try:
        close   = _fetch_close("^VIX", auto_adjust=False)
        vix_val = float(close.iloc[-1])
        detail["VIX"] = round(vix_val, 2)
        vs = _vix_score(vix_val)
        score += vs * 0.4
        detail["VIX得分"] = round(vs, 3)
    except Exception as e:
        detail["VIX"] = f"获取失败: {e}"

    # ── 标普500（权重 40%）──
    try:
        close = _fetch_close("^GSPC")
        chg   = _safe_chg(close, "^GSPC")
        if chg is not None:
            detail["标普500涨跌"] = f"{chg * 100:.2f}%"
            s = _index_score(chg)
            score += s * 0.4
            detail["标普500得分"] = round(s, 3)
        else:
            detail["标普500涨跌"] = "数据不足，已跳过"
    except Exception as e:
        detail["标普500"] = f"获取失败: {e}"

    # ── 纳斯达克（权重 20%）──
    try:
        close = _fetch_close("^IXIC")
        chg   = _safe_chg(close, "^IXIC")
        if chg is not None:
            detail["纳斯达克涨跌"] = f"{chg * 100:.2f}%"
            s = _index_score(chg)
            score += s * 0.2
            detail["纳斯达克得分"] = round(s, 3)
        else:
            detail["纳斯达克涨跌"] = "数据不足，已跳过"
    except Exception as e:
        detail["纳斯达克"] = f"获取失败: {e}"

    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
