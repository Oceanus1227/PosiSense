"""
飞书 Webhook 推送模块
"""

import requests
import yaml
import os
from datetime import datetime

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _pos_label(pos: int) -> tuple[str, str]:
    if pos >= 80:   return "🟢 积极进攻", "green"
    elif pos >= 60: return "🟡 标准持仓", "yellow"
    elif pos >= 40: return "🟠 谨慎持仓", "orange"
    elif pos >= 20: return "🔴 轻仓防守", "red"
    else:           return "⚫ 空仓观望", "grey"


def _score_bar(s: float) -> str:
    filled = max(0, min(10, int((s + 1.0) * 5)))
    return "█" * filled + "░" * (10 - filled)


def _build_markdown(result: dict, gs: dict, gsc: dict, ash: dict, asc: dict) -> str:
    pos   = result["position"]
    score = result["composite_score"]
    label, _ = _pos_label(pos)
    lines = []

    # ── 仓位建议 ──
    lines.append(f"## 建议仓位：{pos}%  {label}")
    if result.get("vix_override"):
        lines.append("⚠️ **VIX 熔断已触发，仓位已强制调整**")
    lines.append(f"综合得分：`{score:+.3f}`")
    lines.append("")

    # ── 各层得分 ──
    lines.append("**📐 各层得分**")
    for layer, s in result["layer_scores"].items():
        bar = _score_bar(s)
        lines.append(f"`{layer}` [{bar}] `{s:+.3f}`")
    lines.append("")

    # ── 全球市场 ──
    lines.append("---")
    lines.append("**🌐 全球市场**")
    vix_val = gs["detail"].get("VIX", "N/A")
    lines.append(f"VIX：`{vix_val}`")
    for key in ["S&P500", "NASDAQ", "道琼斯", "美元指数"]:
        val = gs["detail"].get(key, "N/A")
        lines.append(f"{key}：`{val}`")
    lines.append("")

    if gsc.get("strong"):
        lines.append(f"强势行业：{', '.join(gsc['strong'])}")
    if gsc.get("weak"):
        lines.append(f"弱势行业：{', '.join(gsc['weak'])}")
    lines.append("")

    # ── A股市场 ──
    lines.append("---")
    lines.append("**🇨🇳 A股市场**")
    for key in ["上证指数", "深证成指", "创业板指"]:
        val = ash["detail"].get(key, "N/A")
        lines.append(f"{key}：`{val}`")

    vol = ash["detail"].get("成交量变化", "N/A")
    lines.append(f"成交量变化：`{vol}`")
    lines.append("")

    if asc.get("strong"):
        lines.append(f"强势行业：{', '.join(asc['strong'])}")
    if asc.get("weak"):
        lines.append(f"弱势行业：{', '.join(asc['weak'])}")

    return "\n".join(lines)


def send_feishu(result: dict, gs: dict, gsc: dict, ash: dict, asc: dict) -> bool:
    """发送飞书卡片消息，返回 True 表示成功"""
    if not cfg["feishu"].get("enabled", False):
        print("ℹ️  飞书推送已禁用")
        return False

    webhook = os.environ.get("FEISHU_WEBHOOK", cfg["feishu"].get("webhook", ""))
    if not webhook:
        print("⚠️  未配置飞书 Webhook，跳过推送")
        return False

    label, color = _pos_label(result["position"])
    md_content   = _build_markdown(result, gs, gsc, ash, asc)
    now_str      = datetime.now().strftime("%Y-%m-%d %H:%M")

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 PosiSense 仓位报告  |  {now_str}",
                },
                "template": color,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": md_content,
                    },
                },
            ],
        },
    }

    try:
        resp = requests.post(webhook, json=card, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 or data.get("StatusCode") == 0:
            print("✅ 飞书推送成功")
            return True
        else:
            print(f"⚠️  飞书返回异常: {data}")
            return False
    except Exception as e:
        print(f"❌ 飞书推送失败: {e}")
        return False
