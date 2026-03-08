import pandas as pd
import yfinance as yf
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _fetch_close(ticker: str) -> pd.Series:
    """下载单 ticker，始终返回干净的一维 Series"""
    df = yf.download(ticker, period="5d", interval="1d",
                     progress=False, auto_adjust=True)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna()


def get_global_sectors() -> dict:
    tickers = cfg["global_sector_tickers"]
    strong_thr = cfg["global_sector"]["strong_threshold"] / 100
    weak_thr   = cfg["global_sector"]["weak_threshold"]   / 100
    strong, weak = [], []
    detail = {}

    for name, ticker in tickers.items():
        try:
            close = _fetch_close(ticker)
            if len(close) < 2:
                continue
            chg = float(close.iloc[-1] - close.iloc[-2]) / float(close.iloc[-2])
            detail[name] = f"{chg * 100:.2f}%"
            if chg > strong_thr:
                strong.append(name)
            elif chg < weak_thr:
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
