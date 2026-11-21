#!/usr/bin/env python3
"""Проверка живых метрик GitHub API для тем Учебника (проход профессора 2026-09-27)."""
import json
import urllib.request

REPOS = [
    "checkstyle/checkstyle",
    "pollen-robotics/microduck_rl",
    "pollen-robotics/microduck",
    "Lakr233/vphone-cli",
]
for r in REPOS:
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/" + r,
            headers={"User-Agent": "hermes-professor", "Accept": "application/vnd.github+json"},
        )
        d = json.load(urllib.request.urlopen(req, timeout=25))
        lic = (d.get("license") or {}).get("spdx_id")
        print(
            "%-32s stars=%-7s forks=%-6s issues=%-5s lic=%-12s lang=%-10s pushed=%s created=%s"
            % (
                d.get("full_name"),
                d.get("stargazers_count"),
                d.get("forks_count"),
                d.get("open_issues_count"),
                lic,
                d.get("language"),
                d.get("pushed_at"),
                d.get("created_at"),
            )
        )
        print("    ", (d.get("description") or "")[:220])
    except Exception as e:  # noqa: BLE001
        print(r, "ERROR", e)
