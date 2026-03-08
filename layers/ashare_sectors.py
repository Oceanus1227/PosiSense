import akshare as ak
import numpy as np
import pandas as pd
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def get_ashare_sectors() -> dict:
    """
    A股行业走势评分（东方财富行业板块，排名制）
    返回：
        score  : float，范围 -1.0 ~ +1.0
        strong : list，涨幅前 N 行业（含涨跌幅）
        weak   : list，跌幅前 N 行业（含涨跌幅）
        detail : dict，全部行业涨跌幅
        rank   : list，全部行业排名列表
    """
    score  = 0.0
    strong, weak = [], []
    detail = {}
    rank   = []

    top_n = cfg["ashare_sector"].get("top_n", 5)

    try:
        df = ak.stock_board_industry_name_em()
        df["涨跌幅"] = pd.to_numeric(df["涨跌幅"], errors="coerce")
        df = df.dropna(subset=["涨跌幅"]).sort_values("涨跌幅", ascending=False).reset_index(drop=True)

        total = len(df)

        # ── 全部行业排名列表 ──────────────────────────
        for i, row in df.iterrows():
            name = row["板块名称"]
            chg  = row["涨跌幅"]
            detail[name] = f"{chg:+.2f}%"
            rank.append({
                "rank": i + 1,
                "name": name,
                "chg":  round(float(chg), 2),
            })

        # ── 强势 / 弱势 Top N ────────────────────────
        for item in rank[:top_n]:
            strong.append(f"{item['name']} ({item['chg']:+.2f}%)")
        for item in rank[-top_n:]:
            weak.insert(0, f"{item['name']} ({item['chg']:+.2f}%)")

        # ── 评分：用行业涨跌幅的加权平均映射到 -1~+1 ─
        top_mean    = df["涨跌幅"].iloc[:top_n].mean()
        bottom_mean = df["涨跌幅"].iloc[-top_n:].mean()
        mid_mean    = df["涨跌幅"].mean()

        # 综合得分：整体均值为主，头尾分化为辅
        raw = mid_mean * 0.5 + (top_mean + bottom_mean) / 2 * 0.5
        # 映射：±3% 对应 ±1.0
        score = float(np.interp(raw, [-3.0, -1.5, -0.3, 0.3, 1.5, 3.0],
                                     [-1.0, -0.5,  0.0, 0.0, 0.5, 1.0]))
        score = round(score, 3)

    except Exception as e:
        detail["错误"] = str(e)

    return {
        "score":  score,
        "strong": strong,
        "weak":   weak,
        "detail": detail,
        "rank":   rank,
    }
