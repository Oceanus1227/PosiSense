import numpy as np
import yfinance as yf
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _index_score(chg: float) -> float:
    """指数涨跌幅（小数）→ 得分，连续映射"""
    return float(np.interp(chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30]))


def get_global_sentiment() -> dict:
    """
    全球宏观情绪评分
    数据来源：标普500、纳斯达克、VIX
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细
    """
    score  = 0.0
    detail = {}

    # ── 标普500 ──────────────────────────────────
    try:
        df = yf.download("^GSPC", period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        chg = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2])
        detail["标普500涨跌"] = f"{chg * 100:.2f}%"
        s = _index_score(chg) * 1.5   # 标普权重更高
        score += s
        detail["标普500得分"] = round(s, 3)
    except Exception as e:
        detail["标普500"] = f"获取失败: {e}"

    # ── 纳斯达克 ─────────────────────────────────
    try:
        df = yf.download("^IXIC", period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        chg = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2])
        detail["纳斯达克涨跌"] = f"{chg * 100:.2f}%"
        s = _index_score(chg)
        score += s
        detail["纳斯达克得分"] = round(s, 3)
    except Exception as e:
        detail["纳斯达克"] = f"获取失败: {e}"

    # ── VIX 恐慌指数 ─────────────────────────────
    try:
        df = yf.download("^VIX", period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        vix_val = float(close.iloc[-1])
        detail["VIX"] = round(vix_val, 2)
        # VIX < 15 乐观加分，> 30 恐慌减分
        vix_score = float(np.interp(vix_val,
            [12,   15,   20,    25,    30,    40  ],
            [0.20, 0.10, 0.00, -0.10, -0.20, -0.30]))
        score += vix_score
        detail["VIX得分"] = round(vix_score, 3)
    except Exception as e:
        detail["VIX"] = f"获取失败: {e}"

    # ── 归一化 ────────────────────────────────────
    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
