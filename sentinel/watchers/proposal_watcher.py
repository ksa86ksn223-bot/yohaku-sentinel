"""sentinel/watchers/proposal_watcher.py
② AI提案リスト 未確認3件以上 → 週次Notion通知
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

def check(config, notion_token, proposal_db_id):
    if not config.get("enabled", True):
        return None
    threshold = config.get("threshold", 3)
    status_unchecked = config.get("status_unchecked", "未確認")
    payload = {
        "filter": {
            "property": "判定",
            "select": {"equals": status_unchecked}
        },
        "page_size": 100
    }
    try:
        resp = requests.post(
            f"{NOTION_API_URL}/databases/{proposal_db_id}/query",
            headers=_headers(notion_token),
            json=payload,
            timeout=15
        )
        if not resp.ok:
            return None
        results = resp.json().get("results", [])
        count = len(results)
        if count < threshold:
            return None
        titles = []
        for p in results[:5]:
            t = p.get("properties", {}).get("タイトル", {}).get("title", [])
            titles.append(f"- {t[0]['text']['content'] if t else '(タイトルなし)'}")
        return {
            "title": f"[SENTINEL] AI提案リスト 未確認 {count}件",
            "memo": f"未確認が {count} 件あります。\n" + "\n".join(titles),
            "severity": "WARNING"
        }
    except:
        return None
