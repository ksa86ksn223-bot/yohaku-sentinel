"""sentinel/notifier.py
Notion ガバナンスログへの通知共通処理
"""
from __future__ import annotations
import requests
from datetime import datetime, timezone

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def post_governance_log(token, db_id, title, memo, severity="INFO"):
    now_jst = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    full_memo = f"[{severity}] {now_jst}\n\n{memo}"
    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "タイトル": {"title": [{"text": {"content": title[:200]}}]},
            "メモ": {"rich_text": [{"text": {"content": full_memo[:2000]}}]}
        }
    }
    try:
        resp = requests.post(
            f"{NOTION_API_URL}/pages",
            headers=_headers(token),
            json=payload,
            timeout=15
        )
        return resp.ok
    except Exception as e:
        print(f"[notifier] エラー: {e}")
        return False
