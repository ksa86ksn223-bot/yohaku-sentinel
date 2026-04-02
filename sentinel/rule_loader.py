from __future__ import annotations
import copy
import os
from typing import Optional
import requests

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
RULE_NAME_TO_WATCHER_KEY = {
    "github_watcher": "github",
    "proposal_watcher": "proposal",
    "agent_watcher": "agent_ledger",
    "error_log_watcher": "error_log",
}

def _headers(token):
    return {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"}

def _parse_conditions(condition_str):
    result = {}
    if not condition_str.strip():
        return result
    for part in condition_str.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        k, v = k.strip(), v.strip()
        if v.lower() in ("true", "on"):
            result[k] = True
        elif v.lower() in ("false", "off"):
            result[k] = False
        else:
            try:
                result[k] = int(v)
            except ValueError:
                try:
                    result[k] = float(v)
                except ValueError:
                    result[k] = v
    return result

def _extract_text(prop):
    for field in ("title", "rich_text"):
        items = prop.get(field, [])
        if items:
            return items[0].get("plain_text", "")
    return ""

def fetch_active_rules(token, db_id):
    url = f"{NOTION_API_URL}/databases/{db_id}/query"
    payload = {"filter": {"property": "有効", "select": {"equals": "ON"}}, "page_size": 100}
    results = []
    has_more = True
    start_cursor = None
    while has_more:
        if start_cursor:
            payload["start_cursor"] = start_cursor
        resp = requests.post(url, headers=_headers(token), json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")
    return results

def rule_to_watcher_config(page):
    props = page.get("properties", {})
    rule_name = _extract_text(props.get("ルール名", {}))
    mode_val = props.get("モード", {}).get("select", {})
    mode = mode_val.get("name", "") if mode_val else ""
    condition = _extract_text(props.get("条件", {}))
    target = _extract_text(props.get("対象リポジトリ/DB", {}))
    watcher_key = RULE_NAME_TO_WATCHER_KEY.get(rule_name)
    if not watcher_key:
        print(f"[rule_loader] 未知のルール名をスキップ: '{rule_name}'")
        return None, {}
    cfg = {"enabled": True}
    if mode in ("immediate", "weekly"):
        cfg["mode"] = mode
    if condition:
        cfg.update(_parse_conditions(condition))
    if target:
        targets = [t.strip() for t in target.split(",") if t.strip()]
        if targets:
            cfg["repos"] = targets
    return watcher_key, cfg

def load_config_with_rules(base_config, token, rules_db_id):
    if not rules_db_id:
        print("[rule_loader] NOTION_DB_MONITORING_RULES 未設定 → config.yaml を使用")
        return base_config
    try:
        pages = fetch_active_rules(token, rules_db_id)
    except Exception as e:
        print(f"[rule_loader] 監視ルールDB 取得失敗 → config.yaml にフォールバック: {e}")
        return base_config
    if not pages:
        print("[rule_loader] 有効なルールが0件 → config.yaml を使用")
        return base_config
    merged = copy.deepcopy(base_config)
    watchers = merged.setdefault("watchers", {})
    applied = 0
    for page in pages:
        watcher_key, rule_cfg = rule_to_watcher_config(page)
        if not watcher_key:
            continue
        if watcher_key not in watchers:
            watchers[watcher_key] = {}
        watchers[watcher_key].update(rule_cfg)
        applied += 1
        print(f"[rule_loader] ルール適用: {watcher_key} ← {rule_cfg}")
    print(f"[rule_loader] {applied}/{len(pages)} 件のルールを適用しました")
    return merged
