import requests
import yaml
import os

_cfg_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
with open(_cfg_path) as f:
    cfg = yaml.safe_load(f)


def _pos_label(pos: int) -> tuple[str, str]:
    """返回 (标签文字, 卡片颜色模板)"""
    if pos >= 80:
        return "🟢 积极进攻", "green"
    elif pos >= 60:
        return "🟡 标准持仓", "yellow"
    elif pos >= 40:
        return "🟠 谨慎持仓", "orange"
    elif pos >= 20:
        return "🔴 轻仓防守", "red"
    else:
        return "⚫ 空仓观望", "grey"


def _score_bar(s: float) -> str:
    """生成得分进度条"""
    filled = int((s + 1.0) * 5)
    filled = max(0, min(10, filled))
    return "█" * filled + "░" * (10 - filled)


def _build_markdown(result: dict, gs: dict, gsc: dict, ash: dict, asc: dict) -> str:
    """拼装飞书卡片的 Markdown 内容"""
    pos   = result["position"]
    score = result["composite_score"]
    label, _ = _pos_label(pos)

    lines = []

    # ── 仓位建议 ──
    lines.append(f"## 建议仓位：{pos}%　{label}")
    if result.get("vix_override"):
        lines.append("⚠️ VIX 熔断已触发，仓位已强制调整")
    lines.append(f"综合得分：`{score:+.3f}`")
    lines.append("")

    # ── 各层得分 ──
    lines.append("**📐 各层得分**")
    for layer, s in result["layer_scores"].items():
        bar = _score_bar(s)
        lines.append(f"{layer}　[{bar}]　{s:+.3f}")
    lines.append("")

    # ── 全球市场 & A股市场 并排展示 ──
    lines.append("---")
    lines.append("")

    # 全球情绪明细
    gd = gs.get("detail", {})
    sp_chg  = gd.get("标普500涨跌", "—")
    nq_chg  = gd.get("纳斯达克涨跌", "—")
    vix_val = gd.get("VIX", "—")

    # A股情绪明细
    ad = ash.get("detail", {})
    sh_chg = ad.get("上证涨跌", "—")
    sz_chg = ad.get("深证涨跌", "—")
    zt     = ad.get("涨停数", "—")
    dt     = ad.get("跌停数", "—")

    lines.append("**🌐 全球市场**")
    lines.append(f"标普500：{sp_chg}")
    lines.append(f"纳斯达克：{nq_chg}")
    lines.append(f"VIX：{vix_val}")
    lines.append("")
    lines.append("**🇨🇳 A股市场**")
    lines.append(f"上证：{sh_chg}")
    lines.append(f"深证：{sz_chg}")
    lines.append(f"涨停/跌停：{zt} / {dt}")
    lines.append("")

    # ── 行业强弱 ──
    lines.append("---")
    lines.append("")

    g_strong = "、".join(gsc.get("strong", [])) if gsc.get("strong") else "—"
    g_weak   = "、".join(gsc.get("weak", []))   if gsc.get("weak")   else "—"
    a_strong = "、".join(asc.get("strong", [])) if asc.get("strong") else "—"
    a_weak   = "、".join(asc.get("weak", []))   if asc.get("weak")   else "—"

    lines.append(f"**🌐 全球行业**")
    lines.append(f"📈 强势：{g_strong}")
    lines.append(f"📉 弱势：{g_weak}")
    lines.append("")
    lines.append(f"**🇨🇳 A股行业**")
    lines.append(f"📈 强势：{a_strong}")
    lines.append(f"📉 弱势：{a_weak}")
    lines.append("")

    # ── 免责 ──
    lines.append("---")
    lines.append("⚠️ 本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。")

    return "\n".join(lines)


def send_feishu(result: dict, gs: dict, gsc: dict, ash: dict, asc: dict):
    """
    飞书 Webhook 推送（卡片消息）
    参数与 main.py 的调用保持一致：send_feishu(result, gs, gsc, ash, asc)
    """
    webhook_url = cfg.get("feishu", {}).get("webhook_url", "")
    if not webhook_url:
        print("  ⚠️ 未配置飞书 webhook_url，跳过推送")
        return

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    _, color = _pos_label(result["position"])
    title   = f"📊 PosiSense 仓位报告 | {now}"
    content = _build_markdown(result, gs, gsc, ash, asc)

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title":    {"tag": "plain_text", "content": title},
                "template": color
            },
            "elements": [
                {"tag": "markdown", "content": content}
            ]
        }
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        r = resp.json()
        if r.get("code") == 0 or r.get("StatusCode") == 0:
            print("  ✅ 飞书推送成功")
        else:
            print(f"  ⚠️ 飞书返回异常: {r}")
    except Exception as e:
        print(f"  ❌ 飞书推送失败: {e}")
