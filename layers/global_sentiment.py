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


def _fetch_close(ticker: str) -> pd.Series:
    """
    下载单 ticker，始终返回干净的一维 Series（按日期升序）。
    period="10d" 保证节假日/周末后仍有足够交易日。
    """
    df = yf.download(ticker, period="10d", interval="1d",
                     progress=False, auto_adjust=True)
    close = df["Close"]
    # ── 处理 MultiIndex 列（yfinance 新版本常见问题）──
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    # ── 确保索引是 DatetimeIndex ──────────────────────
    close.index = pd.to_datetime(close.index)
    return close.dropna().sort_index()


def _safe_chg(close: pd.Series, ticker: str = "") -> float | None:
    """
    计算最近两个交易日涨跌幅。
    若数据不足 2 条，或最后两条日期间隔 > 5 个自然日，返回 None。
    """
    if len(close) < 2:
        print(f"  [WARN] {ticker} 数据不足 2 条，跳过")
        return None
    last_date = close.index[-1]
    prev_date = close.index[-2]
    gap = (last_date - prev_date).days
    if gap > 5:
        print(f"  [WARN] {ticker} 日期间隔异常: "
              f"{prev_date.date()} → {last_date.date()} ({gap}天)，跳过")
        return None
    return float(close.iloc[-1] - close.iloc[-2]) / float(close.iloc[-2])


def get_global_sentiment() -> dict:
    """
    全球宏观情绪评分
    数据来源：VIX（40%）+ 标普500（40%）+ 纳斯达克（20%）
    """
    score = 0.0
    detail = {}

    # ── VIX 恐慌指数（权重 40%）─────────────────────
    try:
        close = _fetch_close("^VIX")
        vix_val = float(close.iloc[-1])
        detail["VIX"] = vix_val          # 必须是 float，熔断逻辑依赖此值
        vs = _vix_score(vix_val)
        score += vs * 0.4
        detail["VIX得分"] = round(vs, 3)
    except Exception as e:
        detail["VIX"] = f"获取失败: {e}"

    # ── 标普500（权重 40%）──────────────────────────
    try:
        close = _fetch_close("^GSPC")
        chg = _safe_chg(close, "^GSPC")
        if chg is not None:
            detail["标普500涨跌"] = f"{chg * 100:.2f}%"
            s = _index_score(chg)
            score += s * 0.4
            detail["标普500得分"] = round(s, 3)
        else:
            detail["标普500涨跌"] = "数据异常，已跳过"
    except Exception as e:
        detail["标普500"] = f"获取失败: {e}"

    # ── 纳斯达克（权重 20%）─────────────────────────
    try:
        close = _fetch_close("^IXIC")
        chg = _safe_chg(close, "^IXIC")
        if chg is not None:
            detail["纳斯达克涨跌"] = f"{chg * 100:.2f}%"
            s = _index_score(chg)
            score += s * 0.2
            detail["纳斯达克得分"] = round(s, 3)
        else:
            detail["纳斯达克涨跌"] = "数据异常，已跳过"
    except Exception as e:
        detail["纳斯达克"] = f"获取失败: {e}"

    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
