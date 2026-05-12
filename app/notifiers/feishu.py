"""
Feishu (Lark) webhook bot notification backend.

飞书 Webhook 机器人通知后端。
"""

import base64
import hashlib
import hmac
import logging
import time
from datetime import datetime
from typing import Any

import httpx

from app.config import Settings
from app.notifiers.base import NotifierBackend

logger = logging.getLogger(__name__)

# UI text in three languages / 三语 UI 文案
_I18N: dict[str, dict[str, str]] = {
    "en": {
        "sync_ok": "Sync Succeeded",
        "sync_fail": "Sync Failed",
        "header_sync": "HKEX Sync - {status}",
        "header_new": "HKEX New Announcements ({code})",
        "stock_codes": "Stock Codes",
        "mode": "Mode",
        "duration": "Duration",
        "new": "New",
        "skipped": "Skipped",
        "failed": "Failed",
        "error": "Error",
        "retry": "Retry Sync",
        "view": "View",
        "view_all": "View All Announcements",
        "count_new": "{count} new announcements",
        "count_new_single": "1 new announcement",
        "and_more": "... and {count} more",
        "untitled": "Untitled",
    },
    "zh": {
        "sync_ok": "同步成功",
        "sync_fail": "同步失败",
        "header_sync": "港交所同步 - {status}",
        "header_new": "港交所新公告（{code}）",
        "stock_codes": "股票代码",
        "mode": "模式",
        "duration": "耗时",
        "new": "新增",
        "skipped": "跳过",
        "failed": "失败",
        "error": "错误",
        "retry": "重新同步",
        "view": "查看",
        "view_all": "查看全部公告",
        "count_new": "{count} 条新公告",
        "count_new_single": "1 条新公告",
        "and_more": "... 还有 {count} 条",
        "untitled": "无标题",
    },
    "cn": {
        "sync_ok": "同步成功",
        "sync_fail": "同步失败",
        "header_sync": "港交所同步 - {status}",
        "header_new": "港交所新公告（{code}）",
        "stock_codes": "股票代码",
        "mode": "模式",
        "duration": "耗时",
        "new": "新增",
        "skipped": "跳过",
        "failed": "失败",
        "error": "错误",
        "retry": "重新同步",
        "view": "查看",
        "view_all": "查看全部公告",
        "count_new": "{count} 条新公告",
        "count_new_single": "1 条新公告",
        "and_more": "... 还有 {count} 条",
        "untitled": "无标题",
    },
}


def _t(lang: str, key: str, **kwargs: Any) -> str:
    """
    Get translated text for a given key in the specified language.

    获取指定语言的翻译文本。

    Args:
    lang: Language code (en/zh/cn). / 语言代码。
    key: Translation key. / 翻译键。
    **kwargs: Format parameters for the template. / 模板格式化参数。

    Returns:
    str: Translated text. / 翻译文本。

    """
    text = _I18N.get(lang, _I18N["en"]).get(key, _I18N["en"].get(key, key))
    return text.format(**kwargs) if kwargs else text


class FeishuNotifier(NotifierBackend):
    """
    Send notifications via Feishu custom bot webhook.

    通过飞书自定义机器人 Webhook 发送通知。

    Supports interactive card messages with:
    支持的交互卡片消息功能：
    - Sync result cards with status, counts, and duration
      同步结果卡片（状态、计数、耗时）
    - Retry button on failed syncs (links back to the service API)
      失败同步的重试按钮（链接回服务 API）
    - New announcement cards with title, stock code, and HKEX links
      新公告卡片（标题、股票代码、港交所链接）

    """

    def __init__(self, settings: Settings):
        self._webhook_url = settings.NOTIFIER_FEISHU_WEBHOOK
        self._secret = settings.NOTIFIER_FEISHU_SECRET
        self._lang = settings.DEFAULT_LANGUAGE
        self._site_url = settings.SITE_URL

    def _gen_sign(self, timestamp: int) -> str:
        """
        Generate Feishu webhook signature for verification.

        生成飞书 Webhook 签名用于验证。

        Args:
        timestamp: Current Unix timestamp in seconds. / 当前 Unix 时间戳（秒）。

        Returns:
        str: Base64 encoded HMAC-SHA256 signature. / Base64 编码的 HMAC-SHA256 签名。

        """
        string_to_sign = f"{timestamp}\n{self._secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _post(self, payload: dict) -> None:
        """
        Send a POST request to the Feishu webhook.

        向飞书 Webhook 发送 POST 请求。

        Args:
        payload: The JSON payload to send. / 要发送的 JSON 负载。

        """
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(self._webhook_url, json=payload)
                result = resp.json()
                if result.get("code") != 0:
                    logger.warning("Feishu webhook error: %s", result)
                else:
                    logger.info("Feishu notification sent successfully")
        except Exception:
            logger.exception("Failed to send Feishu notification")

    def _build_base_payload(self) -> dict:
        """
        Build the base payload with optional signature.

        构建带可选签名的基础负载。
        """
        payload: dict[str, Any] = {}
        if self._secret:
            timestamp = int(time.time())
            payload["timestamp"] = str(timestamp)
            payload["sign"] = self._gen_sign(timestamp)
        return payload

    def send_sync_result(self, sync_log: Any) -> None:
        """
        Send an interactive card for sync completion.

        发送同步完成的交互卡片。

        Args:
        sync_log: SyncLog ORM instance. / SyncLog ORM 实例。

        """
        status = sync_log.status.value if hasattr(sync_log.status, "value") else str(sync_log.status)
        is_success = status == "success"
        tag_color = "green" if is_success else "red"
        status_text = _t(self._lang, "sync_ok" if is_success else "sync_fail")
        lang = self._lang

        duration = ""
        if sync_log.duration_seconds is not None:
            duration = f"{sync_log.duration_seconds:.1f}s"

        elements = [
            {
                "tag": "column_set",
                "columns": [
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "markdown", "content": f"**{status_text}**"},
                    ]},
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "markdown", "content": f"<font color='{tag_color}'>{status}</font>"},
                    ]},
                ],
            },
            {"tag": "hr"},
            {
                "tag": "column_set",
                "columns": [
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "markdown", "content": f"**{_t(lang,'stock_codes')}**\n{sync_log.stock_codes}"},
                    ]},
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "markdown", "content": f"**{_t(lang,'mode')}**\n{sync_log.mode}"},
                    ]},
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "markdown", "content": f"**{_t(lang,'duration')}**\n{duration or '—'}"},
                    ]},
                ],
            },
            {
                "tag": "column_set",
                "columns": [
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "markdown", "content": f"**{_t(lang,'new')}**\n{sync_log.synced}"},
                    ]},
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "markdown", "content": f"**{_t(lang,'skipped')}**\n{sync_log.skipped}"},
                    ]},
                    {"tag": "column", "width": "weighted", "weight": 1, "elements": [
                        {"tag": "markdown", "content": f"**{_t(lang,'failed')}**\n{sync_log.failed}"},
                    ]},
                ],
            },
        ]

        if sync_log.error:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "markdown",
                "content": f"**{_t(lang,'error')}:** {sync_log.error[:300]}",
            })

        if not is_success:
            elements.append({"tag": "hr"})
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": _t(lang,"retry")},
                        "type": "primary",
                        "url": f"{self._site_url}/?retry={sync_log.stock_codes}",
                    },
                ],
            })

        payload = self._build_base_payload()
        payload["msg_type"] = "interactive"
        payload["card"] = {
            "header": {
                "title": {"tag": "plain_text", "content": _t(lang,"header_sync", status=status_text)},
                "template": "turquoise" if is_success else "red",
            },
            "elements": elements,
        }

        self._post(payload)

    def send_new_announcements(self, announcements: list[Any], stock_code: str) -> None:
        """
        Send a card summarizing newly synced announcements.

        发送新同步公告的摘要卡片。

        Args:
        announcements: List of announcement dicts. / 公告字典列表。
        stock_code: The stock code. / 股票代码。

        """
        if not announcements:
            return

        count = len(announcements)
        lang = self._lang

        # Pick the right language field for title and url
        lang_suffix = lang if lang in ("en", "zh", "cn") else "en"
        lines = []
        for i, ann in enumerate(announcements[:10], 1):
            title = ann.get(f"title_{lang_suffix}", "") or ann.get("title_en", "") or _t(lang,"untitled")
            date_str = ""
            dt = ann.get("announcement_date")
            if dt:
                if isinstance(dt, datetime):
                    date_str = dt.strftime("%Y-%m-%d")
                else:
                    date_str = str(dt)[:10]
            url = ann.get(f"hkex_url_{lang_suffix}", "") or ann.get("hkex_url_en", "")
            link = f"[{_t(lang,'view')}]({url})" if url else ""
            lines.append(f"{i}. **{title}** {date_str} {link}")

        extra = f"\n{_t(lang,'and_more', count=count - 10)}" if count > 10 else ""
        count_text = _t(lang,"count_new", count=count) if count > 1 else _t(lang,"count_new_single")

        elements = [
            {
                "tag": "markdown",
                "content": f"**{count_text}**\n" + "\n".join(lines) + extra,
            },
        ]

        elements.append({"tag": "hr"})
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": _t(lang,"view_all")},
                    "type": "primary",
                    "url": f"{self._site_url}/?stock_code={stock_code}",
                },
            ],
        })

        payload = self._build_base_payload()
        payload["msg_type"] = "interactive"
        payload["card"] = {
            "header": {
                "title": {"tag": "plain_text", "content": _t(lang,"header_new", code=stock_code)},
                "template": "blue",
            },
            "elements": elements,
        }

        self._post(payload)
