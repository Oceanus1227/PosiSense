"""
全球宏观情绪层
数据源：yfinance（VIX + 美股三大指数 + 美元指数）
"""

import numpy as np
import yfinance as yf
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _index_score(chg: float) -> float:
    """指数涨跌幅（小数）→ 得分 [-0.30, +0.30]"""
    return float(np.interp(
        chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30],
    ))


def _vix_score(vix_val: float) -> float:
    """VIX 值 → 得分 [-0.40, +0.10]，带异常值检测"""
    # 异常值检测：VIX正常范围 5-100
    if vix_val > 100 or vix_val < 5:
        print(f"  ⚠️  VIX异常值检测: {vix_val}，使用历史均值20")
        vix_val = 20  # 使用历史均值作为备用
    
    return float(np.interp(
        vix_val,
        [12,   18,   20,   25,    30,    40],
        [0.10, 0.05, 0.00, -0.10, -0.25, -0.40],
    ))


def _get_latest_chg(ticker: str) -> float | None:
    """获取某 ticker 最近一日涨跌幅"""
    try:
        df = yf.download(ticker, period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        if len(close) < 2:
            return None
        return float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2])
    except Exception:
        return None


def _get_vix() -> float | None:
    """获取最新 VIX 收盘值"""
    try:
        df = yf.download("^VIX", period="5d", interval="1d",
                         progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        return float(close.iloc[-1]) if len(close) >= 1 else None
    except Exception:
        return None


def get_global_sentiment() -> dict:
    """
    全球宏观情绪评分
    返回：score (-1.0 ~ +1.0), detail
    """
    score = 0.0
    detail = {}
    
    # 记录原始值用于一致性检查
    vix_value = None
    sp500_chg = None

    # ── VIX ───────────────────────────────────────
    vix_val = _get_vix()
    if vix_val is not None:
        vix_value = vix_val
        detail["VIX"] = round(vix_val, 2)
        
        # 异常值检测
        if vix_val > 100 or vix_val < 5:
            print(f"  ⚠️  VIX数据异常: {vix_val}，可能为节假日/数据源错误")
            detail["VIX"] = f"{vix_val}(异常，按20处理)"
        
        vs = _vix_score(vix_val)
        score += vs
        detail["VIX得分"] = round(vs, 3)
    else:
        detail["VIX"] = "获取失败"

    # ── 美股三大指数 ──────────────────────────────
    us_indices = {
        "S&P500": "^GSPC",
        "NASDAQ": "^IXIC",
        "道琼斯": "^DJI",
    }
    us_changes = []
    for name, ticker in us_indices.items():
        chg = _get_latest_chg(ticker)
        if chg is not None:
            detail[name] = f"{chg * 100:.2f}%"
            us_changes.append(chg)
            if name == "S&P500":
                sp500_chg = chg * 100  # 记录用于一致性检查
        else:
            detail[name] = "获取失败"

    if us_changes:
        avg = sum(us_changes) / len(us_changes)
        us_s = _index_score(avg)
        score += us_s
        detail["美股均涨跌得分"] = round(us_s, 3)

    # ── 数据一致性校验 ─────────────────────────────
    # VIX与标普500方向一致性检查
    if vix_value and sp500_chg:
        # VIX极高(>40)但股市上涨(>1%)，可能是数据异常
        if vix_value > 40 and sp500_chg > 1.0:
