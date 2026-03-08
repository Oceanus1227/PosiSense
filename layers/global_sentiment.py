import numpy as np
import akshare as ak
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _index_score(chg: float) -> float:
    """
    指数涨跌幅 → 得分（连续映射）
    -2% → -0.30,  0% → 0.00,  +2% → +0.30
    """
    return float(np.interp(chg,
        [-0.02, -0.010, -0.003, 0.003, 0.010, 0.02],
        [-0.30, -0.15,   0.00,  0.00,  0.15,  0.30]))


def _get_index_chg(symbol: str) -> float | None:
    """获取 A股指数最近一日涨跌幅（小数形式）"""
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        df = df.dropna(subset=["close"])
        if len(df) < 2:
            return None
        chg = (df["close"].iloc[-1] - df["close"].iloc[-2]) / df["close"].iloc[-2]
        return float(chg)
    except Exception:
        return None


def get_ashare_sentiment() -> dict:
    """
    A股市场情绪评分
    数据来源：上证、深证、创业板指数 + 市场成交量
    返回：
        score  : float，范围 -1.0 ~ +1.0
        detail : dict，各指标明细
    """
    score = 0.0
    detail = {}

    # ── A股三大指数（连续映射）───────────────────
    indices = {
        "上证指数": "sh000001",
        "深证成指": "sz399001",
        "创业板指": "sz399006",
    }
    index_changes = []
    for name, symbol in indices.items():
        chg = _get_index_chg(symbol)
        if chg is not None:
            detail[name] = f"{chg * 100:.2f}%"
            index_changes.append(chg)

    if index_changes:
        avg = sum(index_changes) / len(index_changes)
        idx_score = _index_score(avg)
        score += idx_score
        detail["A股均涨跌得分"] = round(idx_score, 3)

    # ── 市场成交量情绪（沪深两市合计）────────────
    try:
        df_vol = ak.stock_zh_index_daily(symbol="sh000001")
        df_vol = df_vol.dropna(subset=["volume"])
        if len(df_vol) >= 10:
            recent_vol  = df_vol["volume"].iloc[-1]
            avg_vol_10  = df_vol["volume"].iloc[-10:].mean()
            vol_ratio   = recent_vol / avg_vol_10  # 1.0 = 正常量

            detail["成交量比(近1/均10)"] = round(float(vol_ratio), 2)

            # 量比 > 1.2 放量加分，< 0.8 缩量减分
            vol_score = float(np.interp(vol_ratio,
                [0.5,  0.8,  1.0,  1.2,  1.5],
                [-0.20, -0.10, 0.00, 0.10, 0.20]))
            score += vol_score
            detail["成交量得分"] = round(vol_score, 3)

    except Exception as e:
        detail["成交量"] = f"获取失败: {e}"

    # ── 归一化 ────────────────────────────────────
    score = max(-1.0, min(1.0, round(score, 3)))
    return {"score": score, "detail": detail}
