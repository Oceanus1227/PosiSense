"""
全球宏观情绪层
数据源：
  - VIX 恐慌指数（yfinance）
  - 美股三大指数 S&P500 / NASDAQ / DJI（yfinance）
  - 美元指数 DXY（yfinance）
"""

import numpy as np
import yfinance as yf
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


# ── 工具函数 ─────────────────────────────────────────

def _index_score(chg: float) -> float:
    """指数涨跌幅（小数）→ 得分，连续映射到 [-0.30, +0.30]"""
    return float(np.interp(
        chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30],
    ))


def _vix_score(vix_val: float) -> float:
    """VIX 值 → 得分，连续映射到 [-0.40, +0.10]"""
    return float(np.interp(
        vix_val,
        [12, 18, 20, 25, 30, 40],
        [0.10, 0.05, 0.00, -0.10, -0.25, -0.40],
    ))


def _get_latest_chg(ticker: str) -> float | None:
    """获取某 ticker 最近一日涨跌幅（小数）"""
    try:
        df = yf.download(ticker, period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        if len(close) < 2:
            return None
        chg = (float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2])
        return chg
    except Exception:
        return None


def _get_vix() -> float | None:
    """获取最新 VIX 收盘值"""
    try:
        df = yf.download("^VIX", period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        if len(close) < 1:
            return None
        return float(close.iloc[-1])
    except Exception:
        return None


# ── 主函数 ───────────────────────────────────────────

def get_global_sentiment() -> dict:
    """
    全球宏观情绪评分
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细
    """
    score = 0.0
    detail = {}

    # ── VIX 恐慌指数 ──────────────────────────────
    vix_val = _get_vix()
    if vix_val is not None:
        detail["VIX"] = round(vix_val, 2)
        vs = _vix_score(vix_val)
        score += vs
        detail["VIX得分"] = round(vs, 3)
    else:
        detail["VIX"] = "获取失败"

    # ── 美股三大指数 ──────────────────────────────
    us_indices = {
        "S&P500":  "^GSPC",
        "NASDAQ":  "^IXIC",
        "道琼斯":  "^DJI",
    }
    us_changes = []
    for name, ticker in us_indices.items():
        chg = _get_latest_chg(ticker)
        if chg is not None:
            detail[name] = f"{chg * 100:.2f}%"
            us_changes.append(chg)
        else:
            detail[name] = "获取失败"

    if us_changes:
        avg_chg = sum(us_changes) / len(us_changes)
        us_s = _index_score(avg_chg)
        score += us_s
        detail["美股均涨跌得分"] = round(us_s, 3)

    # ── 美元指数 DXY（反向指标）────────────────────
    dxy_chg = _get_latest_chg("DX-Y.NYB")
    if dxy_chg is not None:
        detail["美元指数"] = f"{dxy_chg * 100:.2f}%"
        # 美元走强 → 对新兴市场偏负面，取反
        dxy_s = _index_score(-dxy_chg) * 0.5
        score += dxy_s
        detail["美元得分"] = round(dxy_s, 3)

    # ── 归一化 ────────────────────────────────────
    score = max(-1.0, min(1.0, round(score, 3)))

    return {"score": score, "detail": detail}
