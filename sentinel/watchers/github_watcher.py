"""sentinel/watchers/github_watcher.py
① GitHub Actions ジョブ失敗監視 → 即時Notion通知
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
import requests

GITHUB_API_URL = "https://api.github.com"

def _gh_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def fetch_failed_runs(token, repo, lookback_hours=24):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/runs"
    params = {
        "status": "failure",
        "per_page": 20,
        "created": f">={cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    }
    try:
        resp = requests.get(url, headers=_gh_headers(token), params=params, timeout=15)
        if not resp.ok:
            return []
        return [
            {
                "name": r.get("name", ""),
                "html_url": r.get("html_url", ""),
                "created_at": r.get("created_at", ""),
                "head_branch": r.get("head_branch", ""),
                "repo": repo
            }
            for r in resp.json().get("workflow_runs", [])
        ]
    except:
        return []

def check(config, github_token):
    if not config.get("enabled", True):
        return None
    all_failures = []
    for repo in config.get("repos", []):
        all_failures.extend(fetch_failed_runs(github_token, repo, config.get("lookback_hours", 24)))
    if not all_failures:
        return None
    lines = [f"GitHub Actions 失敗を {len(all_failures)} 件検知しました。\n"]
    for r in all_failures[:10]:
        lines.append(f"- [{r['repo']}] {r['name']} (branch: {r['head_branch']})\n  {r['html_url']}")
    return {
        "title": f"[SENTINEL] GitHub Actions 失敗 {len(all_failures)}件",
        "memo": "\n".join(lines),
        "severity": "CRITICAL" if len(all_failures) >= 3 else "WARNING"
    }
