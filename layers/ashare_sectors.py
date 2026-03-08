"""
A股行业板块强弱评分
数据源：akshare（东方财富行业板块）
"""

import akshare as ak
import pandas as pd
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def get_ashare_sectors() -> dict:
    """
    A股行业走势评分
    返回：
        score  : float，范围 -1.0 ~ +1.0
        strong : list，强势行业（前 top_n）
        weak   : list，弱势行业（前 top_n）
        detail : dict，全部行业涨跌幅
    """
    score  = 0.0
    strong, weak = [], []
    detail = {}

    strong_thr = cfg["ashare_sector"]["strong_threshold"]
    weak_thr   = cfg["ashare_sector"]["weak_threshold"]
    top_n      = cfg["ashare_sector"]["top_n"]

    try:
        df = ak.stock_board_industry_name_em()
        df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        df = df.dropna(subset=["涨跌幅"]).sort_values("涨跌幅", ascending=False)

        total = len(df)
        for _, row in df.iterrows():
            name = row["板块名称"]
            chg  = row["涨跌幅"]
            detail[name] = f"{chg:.2f}%"
            if chg > strong_thr:
                strong.append(name)
            elif chg < weak_thr:
                weak.append(name)

        net   = (len(strong) - len(weak)) / total if total > 0 else 0.0
        score = max(-1.0, min(1.0, round(net, 3)))

    except Exception as e:
        detail["错误"] = str(e)

    return {
        "score":  score,
        "strong": strong[:top_n],
        "weak":   weak[:top_n],
        "detail": detail,
    }
