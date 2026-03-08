import numpy as np
import yfinance as yf
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _get_1d_change(ticker: str) -> float | None:
    """获取单个 ticker 最近一个交易日涨跌幅（小数形式）"""
    try:
        df = yf.download(ticker, period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        if len(df) < 2:
            return None
        close = df["Close"].dropna()
        chg = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]
        return float(chg)
    except Exception:
        return None


def _index_score(chg: float) -> float:
    """
    指数涨跌幅 → 得分（连续映射）
    -2% → -0.30,  0% → 0.00,  +2% → +0.30
    """
    return float(np.interp(chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30]))


def _dxy_score(chg: float) -> float:
    """
    美元指数涨跌幅 → 得分（强美元压制新兴市场）
    -1% → +0.20,  0% → 0.00,  +1% → -0.20
    """
    return float(np.interp(chg,
        [-0.01, -0.005, -0.002, 0.002, 0.005, 0.01],
        [ 0.20,  0.20,   0.10,  -0.10, -0.20, -0.20]))


def get_global_sentiment() -> dict:
    """
    全球宏观情绪评分
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细
    """
    score = 0.0
    detail = {}

    # ── VIX（连续映射）────────────────────────────
    try:
        vix_val = yf.Ticker("^VIX").fast_info["last_price"]
        detail["VIX"] = round(float(vix_val), 2)

        # VIX 15 → +0.40 | 20 → +0.10 | 25 → -0.30 | 35 → -0.60
        vix_score = float(np.interp(vix_val,
            [15,   20,   25,   30,   35  ],
            [0.40, 0.10, -0.10, -0.30, -0.60]))
        score += vix_score
        detail["VIX得分"] = round(vix_score, 3)

    except Exception as e:
        detail["VIX"] = f"获取失败: {e}"

    # ── 美股三大指数（连续映射）───────────────────
    indices = {"SPX": "^GSPC", "NDX": "^IXIC", "DJI": "^DJI"}
    index_changes = []
    for name, ticker in indices.items():
        chg = _get_1d_change(ticker)
        if chg is not None:
            detail[name] = f"{chg * 100:.2f}%"
            index_changes.append(chg)

    if index_changes:
        avg = sum(index_changes) / len(index_changes)
        idx_score = _index_score(avg)
        score += idx_score
        detail["美股均涨跌得分"] = round(idx_score, 3)

    # ── 美元指数 DXY（连续映射）──────────────────
    dxy_chg = _get_1d_change("DX-Y.NYB")
    if dxy_chg is not None:
        detail["DXY"] = f"{dxy_chg * 100:.2f}%"
        dxy_s = _dxy_score(dxy_chg)
        score += dxy_s
        detail["DXY得分"] = round(dxy_s, 3)

    # ── 归一化 ────────────────────────────────────
    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
