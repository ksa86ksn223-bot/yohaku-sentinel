"""sentinel/watchers/error_log_watcher.py
④ GitHub Actions 失敗ログ 週次サマリー通知
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional
import requests

GITHUB_API_URL = "https://api.github.com"

def _gh_headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

def fetch_failed_runs_in_period(token, repo, lookback_hours=168):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    url = f"{GITHUB_API_URL}/repos/{repo}/actions/runs"
    params = {"status": "failure", "per_page": 30, "created": f">={cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')}"}
    try:
        resp = requests.get(url, headers=_gh_headers(token), params=params, timeout=15)
        if not resp.ok:
            return []
        return [{"run_id": r.get("id"), "name": r.get("name",""), "html_url": r.get("html_url",""), "created_at": r.get("created_at",""), "head_branch": r.get("head_branch","")} for r in resp.json().get("workflow_runs", [])]
    except:
        return []

def fetch_failed_job_log_excerpt(token, repo, run_id, excerpt_chars=500):
    jobs_url = f"{GITHUB_API_URL}/repos/{repo}/actions/runs/{run_id}/jobs"
    try:
        resp = requests.get(jobs_url, headers=_gh_headers(token), timeout=15)
        if not resp.ok:
            return ""
        failed_jobs = [j for j in resp.json().get("jobs", []) if j.get("conclusion") == "failure"]
        if not failed_jobs:
            return ""
        job_id = failed_jobs[0].get("id")
        log_resp = requests.get(f"{GITHUB_API_URL}/repos/{repo}/actions/jobs/{job_id}/logs", headers=_gh_headers(token), timeout=15, allow_redirects=True)
        if not log_resp.ok:
            return ""
        return log_resp.text[:excerpt_chars]
    except:
        return ""

def check(config, github_token):
    if not config.get("enabled", True):
        return None
    repos = config.get("repos", [])
    lookback_hours = config.get("lookback_hours", 168)
    excerpt_chars = config.get("log_excerpt_chars", 500)
    if not github_token:
        return None
    all_failures = []
    for repo in repos:
        runs = fetch_failed_runs_in_period(github_token, repo, lookback_hours)
        for run in runs:
            run["repo"] = repo
        all_failures.extend(runs)
    if not all_failures:
        return None
    days = lookback_hours // 24
    lines = [f"過去{days}日間の GitHub Actions 失敗サマリー（{len(all_failures)}件）\n"]
    for run in all_failures[:5]:
        lines.append(f"▼ [{run['repo']}] {run['name']} (branch: {run['head_branch']}, {run['created_at'][:10]})")
        lines.append(f"  URL: {run['html_url']}")
        log = fetch_failed_job_log_excerpt(github_token, run["repo"], run["run_id"], excerpt_chars)
        if log:
            one_line = " / ".join(l.strip() for l in log.splitlines() if l.strip())
            lines.append(f"  エラー抜粋: {one_line[:300]}")
        lines.append("")
    if len(all_failures) > 5:
        lines.append(f"... 他 {len(all_failures) - 5} 件")
    return {"title": f"[SENTINEL] 週次ログサマリー 失敗{len(all_failures)}件", "memo": "\n".join(lines), "severity": "CRITICAL" if len(all_failures) >= 5 else "WARNING"}
