import yfinance as yf
import pandas as pd
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _safe_sector_chg(ticker: str) -> float | None:
    """
    下载行业 ETF，返回最近一个交易日涨跌幅（小数）。
    日期间隔 > 5 天时返回 None，避免跨周计算失真。
    """
    df = yf.download(ticker, period="5d", interval="1d",
                     progress=False, auto_adjust=True)
    if len(df) < 2:
        return None

    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close.index = pd.to_datetime(close.index)
    close = close.dropna().sort_index()

    if len(close) < 2:
        return None

    gap = (close.index[-1] - close.index[-2]).days
    if gap > 5:
        return None

    return float(close.iloc[-1] - close.iloc[-2]) / float(close.iloc[-2])


def get_global_sectors() -> dict:
    """
    全球行业 ETF 强弱评分
    """
    tickers = cfg["global_sector_tickers"]
    strong, weak = [], []
    detail = {}

    for name, ticker in tickers.items():
        try:
            chg = _safe_sector_chg(ticker)
            if chg is None:
                detail[name] = "数据异常，已跳过"
                continue
            detail[name] = f"{chg * 100:.2f}%"
            if chg > 0.005:
                strong.append(name)
            elif chg < -0.005:
                weak.append(name)
        except Exception as e:
            detail[name] = f"获取失败: {e}"

    total = len(tickers)
    net   = (len(strong) - len(weak)) / total if total > 0 else 0.0
    score = max(-1.0, min(1.0, round(net, 3)))

    return {
        "score":  score,
        "strong": strong,
        "weak":   weak,
        "detail": detail,
    }
