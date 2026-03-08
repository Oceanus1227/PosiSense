import time
import random
import akshare as ak
import numpy as np
import pandas as pd
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _fetch_with_retry(retries: int = 5, delay: float = 5.0) -> pd.DataFrame:
    """带重试的 akshare 请求，增加随机延迟避免反爬"""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            # 首次之外的重试，加随机延迟
            if attempt > 1:
                wait = delay + random.uniform(1, 3)
                print(f"  ⏳ 等待 {wait:.1f}s 后重试...")
                time.sleep(wait)
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                return df
            print(f"  ⚠️ A股行业第 {attempt} 次返回空数据，重试中...")
        except Exception as e:
            last_err = e
            print(f"  ⚠️ A股行业第 {attempt} 次请求失败: {e}")
    raise ConnectionError(f"重试 {retries} 次后仍失败: {last_err}")


def get_ashare_sectors() -> dict:
    """
    A股行业走势评分（东方财富行业板块，排名制）
    返回：
        score  : float，范围 -1.0 ~ +1.0
        strong : list，涨幅前 N 行业
        weak   : list，跌幅前 N 行业
        detail : dict，全部行业涨跌幅
        rank   : list，全部行业排名列表
    """
    score = 0.0
    strong, weak = [], []
    detail = {}
    rank = []
    top_n = cfg["ashare_sector"].get("top_n", 5)

    # 从配置读取阈值（百分比，用于得分计算）
    strong_th = cfg["ashare_sector"].get("strong_threshold", 0.5)
    weak_th = cfg["ashare_sector"].get("weak_threshold", -0.5)

    # ★ 修复：首次请求前先等待 3 秒，错开与 ashare_sentiment 的并发
    time.sleep(3)

    try:
        df = _fetch_with_retry(retries=5, delay=5.0)

        # ── 列名容错：兼容不同版本 akshare ──
        col_map = {}
        for col in df.columns:
            if "板块" in col or "行业" in col or "名称" in col:
                col_map["name"] = col
            if "涨跌幅" in col or "涨幅" in col:
                col_map["chg"] = col

        name_col = col_map.get("name", "板块名称")
        chg_col  = col_map.get("chg",  "涨跌幅")
        detail["_columns"] = list(df.columns)

        if chg_col not in df.columns:
            detail["错误"] = f"找不到涨跌幅列，实际列名: {list(df.columns)}"
            return {"score": score, "strong": strong, "weak": weak,
                    "detail": detail, "rank": rank}

        df[chg_col] = pd.to_numeric(df[chg_col], errors="coerce")
        df = (df.dropna(subset=[chg_col])
                .sort_values(chg_col, ascending=False)
                .reset_index(drop=True))

        if df.empty:
            detail["错误"] = "数据为空（可能是非交易时段）"
            return {"score": score, "strong": strong, "weak": weak,
                    "detail": detail, "rank": rank}

        # ── 全部行业排名 ──
        for i, row in df.iterrows():
            name = row[name_col]
            chg  = row[chg_col]
            detail[name] = f"{chg:+.2f}%"
            rank.append({
                "rank": i + 1,
                "name": name,
                "chg":  round(float(chg), 2),
            })

        # ── 强势 / 弱势 Top N ──
        for i, row in df.head(top_n).iterrows():
            strong.append(f"{row[name_col]}({row[chg_col]:+.2f}%)")
        for i, row in df.tail(top_n).iterrows():
            weak.append(f"{row[name_col]}({row[chg_col]:+.2f}%)")

        # ── 得分计算：基于阈值统计强弱行业占比 ──
        total = len(df)
        up_count   = len(df[df[chg_col] > strong_th])
        down_count = len(df[df[chg_col] < weak_th])
        net = (up_count - down_count) / total if total > 0 else 0.0
        score = max(-1.0, min(1.0, round(net, 3)))

    except Exception as e:
        detail["错误"] = f"获取失败: {e}"

    return {"score": score, "strong": strong, "weak": weak,
            "detail": detail, "rank": rank}
