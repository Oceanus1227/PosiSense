import time
import akshare as ak
import numpy as np
import pandas as pd
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _fetch_with_retry(retries: int = 3, delay: float = 3.0) -> pd.DataFrame:
    """带重试的 akshare 请求"""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                return df
            print(f"  ⚠️  A股行业第 {attempt} 次返回空数据，{delay}s 后重试...")
        except Exception as e:
            last_err = e
            print(f"  ⚠️  A股行业第 {attempt} 次请求失败: {e}")
            if attempt < retries:
                time.sleep(delay)
    raise ConnectionError(f"重试 {retries} 次后仍失败: {last_err}")


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
        df = _fetch_with_retry(retries=3, delay=3.0)

        # ── 列名容错：兼容不同版本 akshare 的字段名 ──
        col_map = {}
        for col in df.columns:
            if "板块" in col or "行业" in col or "名称" in col:
                col_map["name"] = col
            if "涨跌幅" in col or "涨幅" in col:
                col_map["chg"] = col

        name_col = col_map.get("name", "板块名称")
        chg_col  = col_map.get("chg",  "涨跌幅")

        # 记录实际列名，方便调试
        detail["_columns"] = list(df.columns)

        if chg_col not in df.columns:
            detail["错误"] = f"找不到涨跌幅列，实际列名: {list(df.columns)}"
            return {"score": score, "strong": strong, "weak": weak, "detail": detail, "rank": rank}

        df[chg_col] = pd.to_numeric(df[chg_col], errors="coerce")
        df = df.dropna(subset=[chg_col]).sort_values(chg_col, ascending=False).reset_index(drop=True)

        if df.empty:
            detail["错误"] = "数据为空（可能是非交易时段）"
            return {"score": score, "strong": strong, "weak": weak, "detail": detail, "rank": rank}

        # ── 全部行业排名列表 ──────────────────────────
        for i, row in df.iterrows():
            name = row[name_col]
            chg  = row[chg_col]
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
        top_mean    = df[chg_col].iloc[:top_n].mean()
        bottom_mean = df[chg_col].iloc[-top_n:].mean()
        mid_mean    = df[chg_col].mean()

        raw   = mid_mean * 0.5 + (top_mean + bottom_mean) / 2 * 0.5
        score = float(np.interp(raw,
            [-3.0, -1.5, -0.3, 0.3, 1.5, 3.0],
            [-1.0, -0.5,  0.0, 0.0, 0.5, 1.0]))
        score = round(score, 3)

    except Exception as e:
        detail["错误"] = str(e)
        print(f"  ❌ A股行业数据最终失败: {e}")

    return {
        "score":  score,
        "strong": strong,
        "weak":   weak,
        "detail": detail,
        "rank":   rank,
    }
