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
        [10,   15,   20,    25,    30,    40,    50  ],
        [1.00, 0.50, 0.00, -0.50, -0.80, -1.00, -1.00]))


def _fetch_close(ticker: str) -> pd.Series:
    """
    下载单 ticker，始终返回干净的一维 Series。
    - period="10d" 保证节假日/周末后仍有足够交易日
    - sort_index()  保证 iloc[-1]=最新交易日，iloc[-2]=前一交易日
    """
    df = yf.download(ticker, period="10d", interval="1d",
                     progress=False, auto_adjust=True)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]          # 多层列 → 取第一列
    return close.dropna().sort_index()    # ← 关键修复


def get_global_sentiment() -> dict:
    """
    全球宏观情绪评分
    数据来源：VIX（40%）+ 标普500（40%）+ 纳斯达克（20%）
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细（VIX 为原始 float，供熔断使用）
    """
    score  = 0.0
    detail = {}

    # ── VIX 恐慌指数（权重 40%）─────────────────────
    try:
        close   = _fetch_close("^VIX")
        vix_val = float(close.iloc[-1])
        detail["VIX"] = vix_val                 # 必须是 float，熔断逻辑依赖此值
        vs = _vix_score(vix_val)
        score += vs * 0.4
        detail["VIX得分"] = round(vs, 3)
    except Exception as e:
        detail["VIX"] = f"获取失败: {e}"

    # ── 标普500（权重 40%）──────────────────────────
    try:
        close = _fetch_close("^GSPC")
        chg   = float(close.iloc[-1] - close.iloc[-2]) / float(close.iloc[-2])
        detail["标普500涨跌"] = f"{chg * 100:.2f}%"
        s = _index_score(chg)
        score += s * 0.4
        detail["标普500得分"] = round(s, 3)
    except Exception as e:
        detail["标普500"] = f"获取失败: {e}"

    # ── 纳斯达克（权重 20%）─────────────────────────
    try:
        close = _fetch_close("^IXIC")
        chg   = float(close.iloc[-1] - close.iloc[-2]) / float(close.iloc[-2])
        detail["纳斯达克涨跌"] = f"{chg * 100:.2f}%"
        s = _index_score(chg)
        score += s * 0.2
        detail["纳斯达克得分"] = round(s, 3)
    except Exception as e:
        detail["纳斯达克"] = f"获取失败: {e}"

    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
