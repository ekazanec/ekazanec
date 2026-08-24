#!/usr/bin/env python3
"""Regenerate README.md: ASCII contribution graph + terminal-style profile card.

Runs in GitHub Actions (uses GITHUB_TOKEN) or locally (uses `gh auth token`).
"""
import json
import os
import subprocess
import urllib.request
from datetime import date

LOGIN = "ekazanec"
SHADES = " .:!*#@"  # 7 levels, index by intensity
QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    followers { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionCount date weekday } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER) {
      totalCount
      nodes { primaryLanguage { name } stargazerCount visibility }
    }
  }
}
"""


def gh_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    return subprocess.check_output(["gh", "auth", "token"], text=True).strip()


def fetch() -> dict:
    body = json.dumps({"query": QUERY, "variables": {"login": LOGIN}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {gh_token()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    return payload["data"]["user"]


def shade(count: int, peak: int) -> str:
    if count == 0:
        return SHADES[0]
    idx = 1 + min(len(SHADES) - 2, (count * (len(SHADES) - 2)) // max(peak, 1))
    return SHADES[idx]


def ascii_graph(cal: dict) -> str:
    weeks = cal["weeks"]
    peak = max((d["contributionCount"] for w in weeks for d in w["contributionDays"]), default=1)
    rows = []
    day_labels = ["    ", "mon ", "    ", "wed ", "    ", "fri ", "    "]
    for weekday in range(7):
        line = day_labels[weekday]
        for w in weeks:
            day = next((d for d in w["contributionDays"] if d["weekday"] == weekday), None)
            line += shade(day["contributionCount"], peak) if day else " "
        rows.append(line)
    # month ruler along the top
    ruler = list(" " * (4 + len(weeks)))
    seen = set()
    for i, w in enumerate(weeks):
        first = w["contributionDays"][0]["date"]
        month = first[5:7]
        if month not in seen and first[8:10] <= "07":
            seen.add(month)
            name = date.fromisoformat(first).strftime("%b").lower()
            for j, ch in enumerate(name):
                if 4 + i + j < len(ruler):
                    ruler[4 + i + j] = ch
    legend = f"    less {SHADES} more · {cal['totalContributions']} contributions · peak {peak}/day"
    return "\n".join(["".join(ruler)] + rows + [legend])


def bar_chart(langs: dict, width: int = 26) -> list[str]:
    total = sum(langs.values()) or 1
    out = []
    for name, n in sorted(langs.items(), key=lambda x: -x[1])[:5]:
        filled = max(1, round(n / total * width))
        pct = n * 100 // total
        out.append(f"{name:<11} {'#' * filled}{'.' * (width - filled)} {pct:>2}%")
    return out


def build(user: dict) -> str:
    cal = user["contributionsCollection"]["contributionCalendar"]
    repos = user["repositories"]
    langs: dict[str, int] = {}
    for n in repos["nodes"]:
        if n["primaryLanguage"]:
            lang = n["primaryLanguage"]["name"]
            langs[lang] = langs.get(lang, 0) + 1
    since = user["createdAt"][:4]
    today = date.today().isoformat()

    with open(os.path.join(os.path.dirname(__file__), "header.txt")) as f:
        header = f.read().rstrip("\n")
    public = sum(1 for n in repos["nodes"] if n["visibility"] == "PUBLIC")
    card = [
        "andrey@gurov ~ $ whoami",
        "-----------------------",
        "Role......: AI-native product designer · SF Bay Area",
        "Craft.....: research-led product design, design systems,",
        "            e-commerce, AI-assisted workflows",
        "Now.......: particle-ocean — 17 sea creatures as three.js",
        "            point clouds, each with its own swimming physics",
        "Portfolio.: https://agurov.com",
        "Live demo.: https://agurov.com/ocean/",
        f"Uptime....: on GitHub since {since}",
        f"Repos.....: {repos['totalCount']} ({public} public — the rest is classified)",
        "",
        "andrey@gurov ~ $ top -o languages",
    ] + bar_chart(langs)

    return f"""```text
{header}
```

```text
{chr(10).join(card)}
```

### contribution flow

```text
{ascii_graph(cal)}
```

<sub>ASCII graph regenerated daily by a GitHub Action · last run {today}</sub>
"""


if __name__ == "__main__":
    readme = build(fetch())
    path = os.path.join(os.path.dirname(__file__), "..", "README.md")
    with open(path, "w") as f:
        f.write(readme)
    print(readme)
