"""
全球宏观情绪层
数据源：yfinance（VIX + 美股三大指数 + 美元指数）
修复：周末自动获取周五数据
"""

import numpy as np
import yfinance as yf
import yaml
import os
from datetime import datetime, timedelta

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
    if vix_val > 100 or vix_val < 5:
        print(f"  ⚠️  VIX异常值检测: {vix_val}，使用历史均值20")
        vix_val = 20
    
    return float(np.interp(
        vix_val,
        [12,   18,   20,   25,    30,    40],
        [0.10, 0.05, 0.00, -0.10, -0.25, -0.40],
    ))


def _is_weekend(dt: datetime) -> bool:
    """检查是否为周末（周六=5, 周日=6）"""
    return dt.weekday() >= 5


def _get_last_trading_date() -> datetime:
    """获取最近一个交易日"""
    today = datetime.now()
    # 如果是周六，回退到周五
    if today.weekday() == 5:
        return today - timedelta(days=1)
    # 如果是周日，回退到周五
    elif today.weekday() == 6:
        return today - timedelta(days=2)
    return today


def _get_latest_chg(ticker: str) -> float | None:
    """获取某 ticker 最近一日涨跌幅（自动处理周末/节假日）"""
    try:
        # 拉取 10 天数据确保覆盖周末/节假日
        df = yf.download(ticker, period="10d", interval="1d",
                         progress=False, auto_adjust=True)
        close = df["Close"].dropna()
        if len(close) < 2:
            return None
        # 返回最后一个有效交易日的涨跌幅
        return float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2])
    except Exception:
        return None


def _get_vix() -> float | None:
    """获取最新 VIX 收盘值（自动处理周末/节假日）"""
    try:
        # 拉取 10 天数据确保覆盖周末/节假日
        df = yf.download("^VIX", period="10d", interval="1d",
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
    
    # 标记是否为周末数据
    last_trading = _get_last_trading_date()
    if _is_weekend(datetime.now()):
        detail["数据日期"] = f"{last_trading.strftime('%Y-%m-%d')} (周五)"
        detail["周末提示"] = "美股休市，使用最近交易日数据"
    
    vix_value = None
    sp500_chg = None

    # VIX
    vix_val = _get_vix()
    if vix_val is not None:
        vix_value = vix_val
        detail["VIX"] = round(vix_val, 2)
        
        if vix_val > 100 or vix_val < 5:
            print(f"  ⚠️  VIX数据异常: {vix_val}，可能为节假日/数据源错误")
            detail["VIX"] = f"{vix_val}(异常，按20处理)"
        
        vs = _vix_score(vix_val)
        score += vs
        detail["VIX得分"] = round(vs, 3)
    else:
        detail["VIX"] = "获取失败"

    # 美股三大指数
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
                sp500_chg = chg * 100
        else:
            detail[name] = "获取失败"

    if us_changes:
        avg = sum(us_changes) / len(us_changes)
        us_s = _index_score(avg)
        score += us_s
        detail["美股均涨跌得分"] = round(us_s, 3)

    # 数据一致性校验
    if vix_value and sp500_chg:
        if vix_value > 40 and sp500_chg > 1.0:
            print(f"  ⚠️  数据不一致: VIX极高({vix_value})但标普500上涨({sp500_chg:.2f}%)")
            detail["数据警告"] = "VIX与股指方向矛盾"

    # 美元指数
    dxy_chg = _get_latest_chg("DX-Y.NYB")
    if dxy_chg is not None:
        detail["美元指数"] = f"{dxy_chg * 100:.2f}%"
        dxy_s = _index_score(-dxy_chg) * 0.5
        score += dxy_s
        detail["美元得分"] = round(dxy_s, 3)
    else:
        detail["美元指数"] = "获取失败"

    # 最终得分
    score = round(score, 3)
    
    # 等级判断
    if score >= 0.3:
        level = "📈 积极"
    elif score <= -0.3:
        level = "📉 消极"
    else:
        level = "➖ 中性"
    
    detail["综合得分"] = score
    detail["情绪等级"] = level
    
    return {
        "score": score,
        "level": level,
        "detail": detail
    }


if __name__ == "__main__":
    result = get_global_sentiment()
    print(f"\n全球宏观情绪评分: {result['score']} ({result['level']})")
    print("\n详情:")
    for k, v in result['detail'].items():
        print(f"  {k}: {v}")
