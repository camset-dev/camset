#!/usr/bin/env python3
"""Append the repository's daily statistics to CSV files (standard library only).

Public series (GITHUB_TOKEN, or none for a dry run): stars, forks, watchers, open issues, release downloads.
Traffic series (STATS_TOKEN, Administration: read): views, clones, referrers, popular paths. Skipped, with a line in the
log, when the token is absent or refused. An API error on a public series exits non-zero.

    GITHUB_REPOSITORY=owner/name python3 repo_stats.py --out DIR [--dry-run]
"""

import argparse
import csv
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"


def get(path, token):
    request = urllib.request.Request(API + path, headers={"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "camset-stats"})
    if token:
        request.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_all(path, token):
    rows, page = [], 1
    while True:
        chunk = get(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}", token)
        rows += chunk
        if len(chunk) < 100:
            return rows
        page += 1


def append(out, name, header, key_cols, rows, dry_run):
    """Add rows whose first key_cols columns are not already in the file; return the rows added."""
    path = os.path.join(out, name)
    seen = set()
    if os.path.exists(path):
        with open(path, newline="") as f:
            seen = {tuple(r[:key_cols]) for r in list(csv.reader(f))[1:]}
    new = []
    for row in rows:
        key = tuple(str(c) for c in row[:key_cols])
        if key not in seen:
            seen.add(key)
            new.append(row)
    print(f"{name}: {len(new)} new row(s)")
    for row in new:
        print("  " + ",".join(str(c) for c in row))
    if new and not dry_run:
        os.makedirs(out, exist_ok=True)
        fresh = not os.path.exists(path)
        with open(path, "a", newline="") as f:
            w = csv.writer(f)
            if fresh:
                w.writerow(header)
            w.writerows(new)
    return new


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="stats", help="folder for the CSV files")
    ap.add_argument("--dry-run", action="store_true", help="print the rows, write nothing")
    args = ap.parse_args()
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        sys.exit("GITHUB_REPOSITORY (owner/name) is not set")
    token = os.environ.get("GITHUB_TOKEN") or None
    traffic_token = os.environ.get("STATS_TOKEN") or None
    today = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")

    try:
        info = get(f"/repos/{repo}", token)
        releases = get_all(f"/repos/{repo}/releases", token)
    except (urllib.error.URLError, OSError, ValueError) as e:
        sys.exit(f"GitHub API error on the public series: {e}")
    downloads = [(today, r["tag_name"], a["name"], a["download_count"]) for r in releases for a in r.get("assets", [])]
    total = sum(d[3] for d in downloads)
    append(args.out, "summary.csv", ["date", "stars", "forks", "watchers", "open_issues", "total_downloads"], 1,
           [(today, info["stargazers_count"], info["forks_count"], info["subscribers_count"], info["open_issues_count"], total)], args.dry_run)
    append(args.out, "downloads.csv", ["date", "tag", "asset", "downloads"], 3, downloads, args.dry_run)

    if not traffic_token:
        print("STATS_TOKEN is not set: skipping views, clones, referrers and paths.")
        return
    try:
        views = get(f"/repos/{repo}/traffic/views", traffic_token)
        clones = get(f"/repos/{repo}/traffic/clones", traffic_token)
        referrers = get(f"/repos/{repo}/traffic/popular/referrers", traffic_token)
        paths = get(f"/repos/{repo}/traffic/popular/paths", traffic_token)
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"STATS_TOKEN was refused or the traffic API failed ({e}): skipping the traffic series.")
        return
    by_day = {}
    for kind, data in (("views", views), ("clones", clones)):
        for d in data.get(kind, []):
            day = d["timestamp"][:10]
            by_day.setdefault(day, {})[kind] = (d["count"], d["uniques"])
    rows = [(day, *v.get("views", (0, 0)), *v.get("clones", (0, 0))) for day, v in sorted(by_day.items())]
    append(args.out, "traffic.csv", ["date", "views", "unique_views", "clones", "unique_clones"], 1, rows, args.dry_run)
    append(args.out, "referrers.csv", ["date", "referrer", "count", "uniques"], 2,
           [(today, r["referrer"], r["count"], r["uniques"]) for r in referrers], args.dry_run)
    append(args.out, "paths.csv", ["date", "path", "count", "uniques"], 2,
           [(today, p["path"], p["count"], p["uniques"]) for p in paths], args.dry_run)


if __name__ == "__main__":
    main()
