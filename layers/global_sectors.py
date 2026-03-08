"""
全球行业 ETF 强弱评分
数据源：yfinance
"""

import yfinance as yf
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def get_global_sectors() -> dict:
    """
    全球行业 ETF 强弱评分
    返回：
        score  : float，范围 -1.0 ~ +1.0
        strong : list，强势行业名称
        weak   : list，弱势行业名称
        detail : dict，各行业涨跌幅
    """
    tickers = cfg["global_sector_tickers"]
    strong_thr = cfg["global_sector"]["strong_threshold"]
    weak_thr   = cfg["global_sector"]["weak_threshold"]

    strong, weak = [], []
    detail = {}

    for name, ticker in tickers.items():
        try:
            df = yf.download(ticker, period="5d", interval="1d",
                             progress=False, auto_adjust=True)
            if len(df) < 2:
                detail[name] = "数据不足"
                continue
            close = df["Close"].dropna()
            chg = (float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2])
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
