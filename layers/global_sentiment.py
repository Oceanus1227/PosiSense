import yfinance as yf
import yaml
import os

# 加载配置
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


def get_global_sentiment() -> dict:
    """
    全球宏观情绪评分
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细
    """
    score = 0.0
    detail = {}

    # ── VIX ──────────────────────────────────────────
    try:
        vix_val = yf.Ticker("^VIX").fast_info["last_price"]
        detail["VIX"] = round(float(vix_val), 2)
        v_safe    = cfg["vix"]["safe"]
        v_caution = cfg["vix"]["caution"]
        v_danger  = cfg["vix"]["danger"]
        if vix_val < v_safe:
            score += 0.40
        elif vix_val < v_caution:
            score += 0.10
        elif vix_val < v_danger:
            score -= 0.30
        else:
            score -= 0.60
    except Exception as e:
        detail["VIX"] = f"获取失败: {e}"

    # ── 美股三大指数 ──────────────────────────────────
    indices = {"SPX": "^GSPC", "NDX": "^IXIC", "DJI": "^DJI"}
    index_changes = []
    for name, ticker in indices.items():
        chg = _get_1d_change(ticker)
        if chg is not None:
            detail[name] = f"{chg * 100:.2f}%"
            index_changes.append(chg)

    if index_changes:
        avg = sum(index_changes) / len(index_changes)
        if avg > 0.010:
            score += 0.30
        elif avg > 0.003:
            score += 0.15
        elif avg > -0.003:
            score += 0.00
        elif avg > -0.010:
            score -= 0.15
        else:
            score -= 0.30

    # ── 美元指数 DXY ──────────────────────────────────
    dxy_chg = _get_1d_change("DX-Y.NYB")
    if dxy_chg is not None:
        detail["DXY"] = f"{dxy_chg * 100:.2f}%"
        # 强美元压制新兴市场
        if dxy_chg > 0.005:
            score -= 0.20
        elif dxy_chg > 0.002:
            score -= 0.10
        elif dxy_chg < -0.005:
            score += 0.20
        elif dxy_chg < -0.002:
            score += 0.10

    # ── 归一化 ────────────────────────────────────────
    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
