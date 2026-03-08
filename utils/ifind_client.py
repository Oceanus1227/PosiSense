"""
iFinD HTTP API 通用客户端
用法：
    from utils.ifind_client import ifind_history, ifind_realtime
"""

import os
import time
import requests
import pandas as pd

_BASE_URL    = "https://quantapi.51ifind.com/api/v1"
_TOKEN_CACHE = {"access_token": None, "expires_at": 0}


def _get_access_token(force_refresh=False) -> str:
    now = time.time()
    if (not force_refresh
        and _TOKEN_CACHE["access_token"]
        and now < _TOKEN_CACHE["expires_at"]):
        return _TOKEN_CACHE["access_token"]

    refresh_token = os.environ.get("IFIND_REFRESH_TOKEN", "").strip()
    if not refresh_token:
        raise RuntimeError("❌ 环境变量 IFIND_REFRESH_TOKEN 未配置")

    resp = requests.post(
        f"{_BASE_URL}/get_access_token",
        headers={"Content-Type": "application/json",
                 "refresh_token": refresh_token},
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    token = body.get("data", {}).get("access_token")
    if not token:
        raise RuntimeError(f"❌ 获取 access_token 失败: {body}")

    _TOKEN_CACHE["access_token"] = token
    _TOKEN_CACHE["expires_at"]   = now + 6 * 86400  # 缓存 6 天
    return token


def _post(endpoint: str, payload: dict) -> dict:
    token = _get_access_token()
    headers = {
        "Content-Type":    "application/json",
        "access_token":    token,
        "Accept-Encoding": "gzip,deflate",
    }
    resp = requests.post(f"{_BASE_URL}/{endpoint}",
                         json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    if result.get("errorcode", -1) != 0:
        raise ValueError(f"iFinD 错误: {result.get('errmsg', result)}")
    return result


def fmt_code(code: str) -> str:
    """'600519' → '600519.SH'"""
    code = code.strip()
    if "." in code:
        return code
    if code.startswith(("6", "5")):
        return f"{code}.SH"
    return f"{code}.SZ"


# ────────────────────────────────────────────
#  历史行情
# ────────────────────────────────────────────
def ifind_history(code: str, start: str, end: str,
                  indicators="open,high,low,close,volume") -> pd.DataFrame:
    """
    获取日K线历史行情
    code: '600519' 或 '600519.SH'
    start/end: 'YYYY-MM-DD'
    返回 DataFrame，列: date, open, high, low, close, volume
    """
    payload = {
        "codes":      fmt_code(code),
        "indicators": indicators,
        "startdate":  start.replace("-", ""),
        "enddate":    end.replace("-", ""),
    }
    result = _post("cmd_history_quotation", payload)

    entry = result["tables"][0]
    times = entry.get("time", [])
    table = entry.get("table", {})

    df = pd.DataFrame(table)
    df.insert(0, "date", times[:len(df)])
    df["date"] = pd.to_datetime(df["date"])
    return df


# ────────────────────────────────────────────
#  实时行情（快照）
# ────────────────────────────────────────────
def ifind_realtime(codes: list[str],
                   indicators="latest,changeRatio,amount,volume") -> pd.DataFrame:
    """
    获取多只股票实时快照
    codes: ['600519', '000858']
    返回 DataFrame，每行一只股票
    """
    codes_str = ",".join(fmt_code(c) for c in codes)
    payload = {
        "codes":      codes_str,
        "indicators": indicators,
    }
    result = _post("cmd_realtime_quotation", payload)

    rows = []
    for entry in result.get("tables", []):
        row = {"code": entry["thscode"]}
        row.update(entry.get("table", {}))
        rows.append(row)
    return pd.DataFrame(rows)


# ────────────────────────────────────────────
#  板块/行业数据（可扩展）
# ────────────────────────────────────────────
def ifind_sector_realtime(sector_code: str = "881001",
                          indicators="latest,changeRatio") -> pd.DataFrame:
    """
    获取行业板块实时行情
    sector_code: 同花顺行业指数代码
    """
    payload = {
        "codes":      sector_code,
        "indicators": indicators,
    }
    result = _post("cmd_realtime_quotation", payload)
    entry = result["tables"][0]
    row = {"code": entry["thscode"]}
    row.update(entry.get("table", {}))
    return pd.DataFrame([row])
