"""sentinel/sentinel.py
YOHAKU Sentinel — OS監視エントリーポイント

実行モード:
  --mode immediate  : GitHub Actions失敗 + エージェント台帳エラーを確認
  --mode weekly     : immediate + AI提案リスト未確認件数も確認
"""
from __future__ import annotations
import argparse
import os
import sys
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from notifier import post_governance_log
from watchers import github_watcher, proposal_watcher, agent_watcher

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")

def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    import re
    def replace_env(match):
        var = match.group(1)
        return os.environ.get(var, f"${{{var}}}")
    raw = re.sub(r"\$\{([^}]+)\}", replace_env, raw)
    return yaml.safe_load(raw)

def run(mode):
    notion_token = os.environ.get("NOTION_TOKEN", "")
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if not notion_token:
        print("[sentinel] ERROR: NOTION_TOKEN が設定されていません")
        sys.exit(1)
    config = load_config()
    notion_cfg = config.get("notion", {})
    gov_db = notion_cfg.get("governance_log_db", "")
    agent_db = notion_cfg.get("agent_ledger_db", "")
    proposal_db = notion_cfg.get("proposal_db", "")
    if not gov_db:
        print("[sentinel] ERROR: NOTION_DB_GOVERNANCE_LOG が設定されていません")
        sys.exit(1)
    notifications = []
    if github_token:
        gh_cfg = config.get("watchers", {}).get("github", {})
        result = github_watcher.check(gh_cfg, github_token)
        if result:
            notifications.append(result)
            print(f"[sentinel] ① GitHub Actions 異常検知: {result['title']}")
        else:
            print("[sentinel] ① GitHub Actions: 異常なし")
    else:
        print("[sentinel] ① GitHub Actions: GITHUB_TOKEN 未設定のためスキップ")
    if agent_db:
        ag_cfg = config.get("watchers", {}).get("agent_ledger", {})
        result = agent_watcher.check(ag_cfg, notion_token, agent_db)
        if result:
            notifications.append(result)
            print(f"[sentinel] ③ エージェント台帳 異常検知: {result['title']}")
        else:
            print("[sentinel] ③ エージェント台帳: 異常なし")
    if mode == "weekly" and proposal_db:
        pr_cfg = config.get("watchers", {}).get("proposal", {})
        result = proposal_watcher.check(pr_cfg, notion_token, proposal_db)
        if result:
            notifications.append(result)
            print(f"[sentinel] ② AI提案リスト 異常検知: {result['title']}")
        else:
            print("[sentinel] ② AI提案リスト: 閾値未満")
    notified = 0
    for notif in notifications:
        success = post_governance_log(
            token=notion_token, db_id=gov_db,
            title=notif["title"], memo=notif["memo"],
            severity=notif.get("severity", "WARNING"))
        if success:
            notified += 1
            print(f"[sentinel] Notion通知完了: {notif['title']}")
    print(f"\n[sentinel] 完了: {len(notifications)}件の異常 / {notified}件通知")
    return notified

def main():
    parser = argparse.ArgumentParser(description="YOHAKU Sentinel — OS監視")
    parser.add_argument("--mode", choices=["immediate", "weekly"], default="immediate")
    args = parser.parse_args()
    run(args.mode)

if __name__ == "__main__":
    main()
