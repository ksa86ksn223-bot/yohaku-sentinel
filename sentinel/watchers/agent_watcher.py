"""sentinel/watchers/agent_watcher.py
③ エージェント台帳 エラー状態 → 即時Notion通知
"""
from __future__ import annotations
from typing import Optional
import requests

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

def _headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json"
    }

def check(config, notion_token, agent_ledger_db_id):
    if not config.get("enabled", True):
        return None
    error_status = config.get("error_status", "エラー")
    payload = {
        "filter": {
            "property": "ステータス",
            "select": {"equals": error_status}
        },
        "page_size": 100
    }
    try:
        resp = requests.post(
            f"{NOTION_API_URL}/databases/{agent_ledger_db_id}/query",
            headers=_headers(notion_token),
            json=payload,
            timeout=15
        )
        if not resp.ok:
            return None
        agents = resp.json().get("results", [])
        count = len(agents)
        if count == 0:
            return None
        lines = [f"エラー状態のエージェントが {count} 件あります。\n"]
        lines.append("【エラーエージェント一覧】")
        for a in agents[:10]:
            n = a.get("properties", {}).get("エージェント名", {}).get("title", [])
            lines.append(f"- {n[0]['text']['content'] if n else '(名前なし)'}")
        if count > 10:
            lines.append(f"... 他 {count - 10} 件")
        return {
            "title": f"[SENTINEL] エージェント台帳 エラー {count}件",
            "memo": "\n".join(lines),
            "severity": "CRITICAL" if count >= 2 else "WARNING"
        }
    except:
        return None
      
