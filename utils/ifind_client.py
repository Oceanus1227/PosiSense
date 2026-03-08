"""
iFinD HTTP API 通用客户端（根据官方手册修正版）
"""
import os
import time
import requests
import pandas as pd

_BASE_URL    = "https://quantapi.51ifind.com/api/v1"
_TOKEN_CACHE = {"access_token": None, "expires_at": 0}


def _get_access_token(force_refresh=False) -> str:
    """获取 access_token（有效期7天）"""
    now = time.time()
    if (not force_refresh
        and _TOKEN_CACHE["access_token"]
        and now < _TOKEN_CACHE["expires_at"]):
        return _TOKEN_CACHE["access_token"]

    refresh_token = os.environ.get("IFIND_REFRESH_TOKEN", "").strip()
    if not refresh_token:
        raise RuntimeError("❌ 环境变量 IFIND_REFRESH_TOKEN 未配置")

    # 修正：根据手册，使用 POST 或 GET 均可
    resp = requests.post(
        f"{_BASE_URL}/get_access_token",
        headers={"Content-Type": "application/json"},
        json={"refresh_token": refresh_token},  # 修正：放 body 更规范
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    
    if body.get("errorcode", -1) != 0:
        raise RuntimeError(f"❌ 获取 access_token 失败: {body.get('errmsg', body)}")
    
    token = body.get("data", {}).get("access_token")
    if not token:
        raise RuntimeError(f"❌ 响应中无 access_token: {body}")

    _TOKEN_CACHE["access_token"] = token
    _TOKEN_CACHE["expires_at"]   = now + 6 * 86400  # 缓存6天（7天有效期）
    return token


def _post(endpoint: str, payload: dict) -> dict:
    """通用 POST 请求"""
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
    
    # 修正：根据手册，错误码判断
    if result.get("errorcode", -1) != 0:
        raise ValueError(f"iFinD 错误 {result.get('errorcode')}: {result.get('errmsg', result)}")
    return result


def fmt_code(code: str) -> str:
    """'600519' → '600519.SH'"""
    code = code.strip()
    if "." in code:
        return code
    if code.startswith(("6", "5", "9")):  # 上交所（包含科创板688/689）
        return f"{code}.SH"
    return f"{code}.SZ"  # 深交所（000/001/002/003/300/301）


# ────────────────────────────────────────────
#  1. 基础数据（新增）
# ────────────────────────────────────────────
def ifind_basic_data(codes: str, indicators: list, **params) -> pd.DataFrame:
    """
    基础数据接口
    对应手册：/basic_data_service
    
    示例：获取ROE等财务指标
    """
    payload = {
        "codes": codes,
        "indipara": [
            {"indicator": ind, "indiparams": params.get(f"{ind}_params", [])}
            for ind in indicators
        ]
    }
    result = _post("basic_data_service", payload)
    
    # 解析返回数据
    tables = result.get("tables", [])
    if not tables:
        return pd.DataFrame()
    
    # 转换为DataFrame
    rows = []
    for entry in tables:
        row = {"code": entry.get("thscode")}
        row.update(entry.get("table", {}))
        rows.append(row)
    return pd.DataFrame(rows)


# ────────────────────────────────────────────
#  2. 日期序列（历史行情）- 修正端点
# ────────────────────────────────────────────
def ifind_history(code: str, start: str, end: str,
                  indicators="open,high,low,close,volume") -> pd.DataFrame:
    """
    获取日K线历史行情
    修正：使用手册中的 date_sequence 接口
    
    code: '600519' 或 '600519.SH'
    start/end: 'YYYY-MM-DD'
    """
    payload = {
        "codes":      fmt_code(code),
        "indicators": indicators,
        "startdate":  start.replace("-", ""),
        "enddate":    end.replace("-", ""),
    }
    # 修正：使用手册中的 date_sequence
    result = _post("date_sequence", payload)

    # 修正：根据手册返回结构解析
    tables = result.get("tables", [])
    if not tables:
        return pd.DataFrame()
    
    entry = tables[0]
    times = entry.get("time", [])
    table = entry.get("table", {})

    df = pd.DataFrame(table)
    if times:
        df.insert(0, "time", times[:len(df)])  # 手册中使用 time 而非 date
        df["time"] = pd.to_datetime(df["time"])
    return df
# ────────────────────────────────────────────
#  3. 实时行情 - 修正端点
# ────────────────────────────────────────────
def ifind_realtime(codes: list[str],
                   indicators="latest,changeRatio,amount,volume") -> pd.DataFrame:
    """
    获取多只股票实时快照
    修正：使用手册中的 real_time_quotation
    
    codes: ['600519', '000858']
    """
    codes_str = ",".join(fmt_code(c) for c in codes)
    payload = {
        "codes":      codes_str,
        "indicators": indicators,
    }
    # 修正：使用手册中的 real_time_quotation
    result = _post("real_time_quotation", payload)
    rows = []
    for entry in result.get("tables", []):
        row = {"code": entry.get("thscode")}
        row.update(entry.get("table", {}))
        rows.append(row)
    return pd.DataFrame(rows)
# ────────────────────────────────────────────
#  4. 板块/行业数据
# ────────────────────────────────────────────
def ifind_sector_realtime(sector_code: str = "881001.TI",
                          indicators="latest,changeRatio") -> pd.DataFrame:
    """
    获取行业板块实时行情
    sector_code: 同花顺行业指数代码（如 881001.TI）
    """
    payload = {
        "codes":      sector_code,
        "indicators": indicators,
    }
    result = _post("real_time_quotation", payload)
    entry = result["tables"][0]
    row = {"code": entry["thscode"]}
    row.update(entry.get("table", {}))
    return pd.DataFrame([row])
