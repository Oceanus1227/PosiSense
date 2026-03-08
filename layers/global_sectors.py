import yfinance as yf
import pandas as pd
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _safe_sector_chg(ticker: str) -> float | None:
    df = yf.download(ticker, period="15d", interval="1d",
                     progress=False, auto_adjust=True)
    if df.empty or len(df) < 2:
        return None

    # 兼容 MultiIndex
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    if "Close" not in df.columns:
        return None

    close = df["Close"].dropna()
    close.index = pd.to_datetime(close.index)
    close = close.sort_index()

    if len(close) < 2:
        return None

    prev = float(close.iloc[-2])
    if prev == 0:
        return None
    return float(close.iloc[-1] - prev) / prev


def get_global_sectors() -> dict:
    tickers = cfg["global_sector_tickers"]
    strong, weak = [], []
    detail = {}

    for name, ticker in tickers.items():
        try:
            chg = _safe_sector_chg(ticker)
            if chg is None:
                detail[name] = "数据不足，已跳过"
                continue
            detail[name] = f"{chg * 100:.2f}%"
            if chg > strong_th:
                strong.append(name)
            elif chg < weak_th:
                weak.append(name)
        except Exception as e:
            detail[name] = f"获取失败: {e}"

    total = len(tickers)
    net   = (len(strong) - len(weak)) / total if total > 0 else 0.0
    score = max(-1.0, min(1.0, round(net, 3)))

    return {"score": score, "strong": strong, "weak": weak, "detail": detail}
