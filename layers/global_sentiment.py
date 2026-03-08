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
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30]))


def _fetch_close(ticker: str) -> pd.Series:
    """下载单 ticker，始终返回干净的一维 Series"""
    df = yf.download(ticker, period="5d", interval="1d",
                     progress=False, auto_adjust=True)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]   # 多层列 → 取第一列
    return close.dropna()


def get_global_sentiment() -> dict:
    score  = 0.0
    detail = {}

    # ── 标普500 ──────────────────────────────────
    try:
        close = _fetch_close("^GSPC")
        chg = float(close.iloc[-1] - close.iloc[-2]) / float(close.iloc[-2])
        detail["标普500涨跌"] = f"{chg * 100:.2f}%"
        s = _index_score(chg) * 1.5
        score += s
        detail["标普500得分"] = round(s, 3)
    except Exception as e:
        detail["标普500"] = f"获取失败: {e}"

    # ── 纳斯达克 ─────────────────────────────────
    try:
        close = _fetch_close("^IXIC")
        chg = float(close.iloc[-1] - close.iloc[-2]) / float(close.iloc[-2])
        detail["纳斯达克涨跌"] = f"{chg * 100:.2f}%"
        s = _index_score(chg)
        score += s
        detail["纳斯达克得分"] = round(s, 3)
    except Exception as e:
        detail["纳斯达克"] = f"获取失败: {e}"

    # ── VIX ──────────────────────────────────────
    try:
        close = _fetch_close("^VIX")
        vix_val = float(close.iloc[-1])
        detail["VIX"] = round(vix_val, 2)
        vix_score = float(np.interp(vix_val,
            [12,   15,   20,    25,    30,    40  ],
            [0.20, 0.10, 0.00, -0.10, -0.20, -0.30]))
        score += vix_score
        detail["VIX得分"] = round(vix_score, 3)
    except Exception as e:
        detail["VIX"] = f"获取失败: {e}"

    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
