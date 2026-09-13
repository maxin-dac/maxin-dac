#!/usr/bin/env python3
"""
README de profil auto-généré :
  1. Stack & Tools  -> badges shields.io entre <!-- STACK:START/END -->
  2. Activity card  -> assets/activity-card.svg (streak + views + repos + last commit)
"""

import os
import re
from datetime import date, timedelta
from xml.sax.saxutils import escape as xml_escape

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GITHUB_USER = "maxin-dac"
README_PATH = "README.md"
MAIN_PROJECT = "world-economic-dashboard"
ACTIVITY_SVG_PATH = "assets/activity-card.svg"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
TIMEOUT = 15

session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1.5,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
session.mount("https://", HTTPAdapter(max_retries=retries))
session.mount("http://", HTTPAdapter(max_retries=retries))

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "maxin-dac-stack-generator",
}
if TOKEN:
    HEADERS["Authorization"] = f"token {TOKEN}"

# ─── BADGES STACK ─────────────────────────────────────────────────────────────
BADGE_MAP = {
    "python":    ("Python",    "3776AB", "python"),
    "sql":       ("SQL",       "4479A1", ""),
    "pandas":    ("Pandas",    "150458", "pandas"),
    "numpy":     ("NumPy",     "013243", ""),
    "plotly":    ("Plotly",    "3F4F75", "plotly"),
    "streamlit": ("Streamlit", "FF4B4B", "streamlit"),
    "powerbi":   ("Power BI",  "F2C811", "powerbi"),
    "excel":     ("Excel",     "217346", "microsoftexcel"),
    "git":       ("Git",       "F05032", "git"),
    "github":    ("GitHub",    "181717", "github"),
    "vscode":    ("VS Code",   "007ACC", "visualstudiocode"),
    "azure":     ("Azure",     "0078D4", "microsoftazure"),
    "copilot":   ("Copilot",   "000000", "githubcopilot"),
}

DISPLAY_ORDER = [
    "python", "sql", "pandas", "numpy", "plotly",
    "streamlit", "powerbi", "excel",
    "git", "github", "vscode", "azure", "copilot",
]

REQ_KEYWORDS = {
    "streamlit": ["streamlit"],
    "plotly":    ["plotly"],
    "pandas":    ["pandas"],
    "numpy":     ["numpy"],
    "sql":       ["sqlalchemy", "pyodbc", "pymssql", "psycopg"],
    "azure":     ["azure"],
}

LANG_ALIASES = {"shell": "bash", "javascript": "js", "typescript": "ts"}

KNOWN_TECHS = set(BADGE_MAP) | set(REQ_KEYWORDS)

# ─── API GITHUB ───────────────────────────────────────────────────────────────

def safe_get(url, params=None, raw=False):
    headers = dict(HEADERS)
    if raw:
        headers["Accept"] = "application/vnd.github.v3.raw"
    try:
        return session.get(url, headers=headers, params=params, timeout=TIMEOUT)
    except requests.exceptions.ConnectionError as e:
        print(f"  ⚠️  Erreur réseau : {url}\n      {e}")
        return None
    except requests.exceptions.Timeout:
        print(f"  ⚠️  Timeout : {url}")
        return None


def get_repos(username):
    url = f"https://api.github.com/users/{username}/repos"
    params = {"per_page": 100, "sort": "updated", "type": "public"}
    resp = safe_get(url, params=params)
    if resp is None or resp.status_code != 200:
        status = resp.status_code if resp is not None else "aucune réponse"
        raise SystemExit(f"❌ Repos introuvables (status: {status}).")
    repos = resp.json()
    return [r for r in repos if not r["fork"] and not r["archived"]]


def get_repo_languages(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    resp = safe_get(url)
    return resp.json() if (resp is not None and resp.status_code == 200) else {}


def get_file_content(owner, repo, path):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    resp = safe_get(url, raw=True)
    return resp.text if (resp is not None and resp.status_code == 200) else None

# ─── DÉTECTION STACK ──────────────────────────────────────────────────────────

def detect_from_requirements(content):
    detected = set()
    content_lower = content.lower()
    for tech, keywords in REQ_KEYWORDS.items():
        for kw in keywords:
            if kw in content_lower:
                detected.add(tech)
                break
    return detected


def detect_from_repo(repo):
    detected = set()
    owner = repo["owner"]["login"]
    name = repo["name"]

    for lang in get_repo_languages(owner, name):
        key = LANG_ALIASES.get(lang.lower(), lang.lower())
        if key in KNOWN_TECHS:
            detected.add(key)

    req = get_file_content(owner, name, "requirements.txt")
    if req:
        detected |= detect_from_requirements(req)
    else:
        pyproject = get_file_content(owner, name, "pyproject.toml")
        if pyproject:
            detected |= detect_from_requirements(pyproject)

    if get_file_content(owner, name, ".streamlit/config.toml"):
        detected.add("streamlit")

    for topic in repo.get("topics", []):
        t = topic.lower().replace("-", "")
        if t in KNOWN_TECHS:
            detected.add(t)

    return detected


def make_badge(label, color, logo):
    label_enc = label.replace(" ", "%20").replace("-", "--")
    if logo == "powerbi":
        logo_qs = "&logo=powerbi&logoColor=black"
    elif logo:
        logo_qs = f"&logo={logo}&logoColor=white"
    else:
        logo_qs = ""
    return f"![{label}](https://img.shields.io/badge/{label_enc}-{color}?style=for-the-badge{logo_qs})"


def generate_stack_markdown(all_techs):
    badges = [make_badge(*BADGE_MAP[t]) for t in DISPLAY_ORDER if t in all_techs]
    if not badges:
        return "_Stack auto-détecté : aucun repo public pour l'instant._"
    return " ".join(badges)

# ─── DONNÉES D'ACTIVITÉ ───────────────────────────────────────────────────────

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""


def fetch_streak_data():
    """Total contributions + streaks via GraphQL (token requis)."""
    if not TOKEN:
        print("  ⚠️  Pas de token : données de streak non récupérées.")
        return None
    try:
        resp = session.post(
            "https://api.github.com/graphql",
            headers={**HEADERS, "Accept": "application/json"},
            json={"query": GRAPHQL_QUERY, "variables": {"login": GITHUB_USER}},
            timeout=TIMEOUT,
        )
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️  GraphQL injoignable : {e}")
        return None
    if resp.status_code != 200:
        print(f"  ⚠️  GraphQL status {resp.status_code}.")
        return None

    cal = resp.json()["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    counts = {
        date.fromisoformat(d["date"]): d["contributionCount"]
        for week in cal["weeks"] for d in week["contributionDays"]
    }

    today = date.today()
    # Streak actuel (aujourd'hui, ou hier si pas encore de contribution aujourd'hui)
    cur, d = 0, today
    if counts.get(d, 0) == 0:
        d -= timedelta(days=1)
    while counts.get(d, 0) > 0:
        cur += 1
        d -= timedelta(days=1)

    # Plus long streak + premières/dernières dates
    longest = run = 0
    ls_start = ls_end = run_start = None
    for d in sorted(counts):
        if counts[d] > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > longest:
                longest, ls_start, ls_end = run, run_start, d
        else:
            run = 0

    active = [d for d in counts if counts[d] > 0]
    return {
        "total": cal["totalContributions"],
        "since": min(active),
        "current": cur,
        "today": today,
        "longest": longest,
        "ls_start": ls_start,
        "ls_end": ls_end,
    }


def fetch_profile_views():
    """Lit le compteur komarev directement sur le SVG du badge."""
    resp = safe_get(f"https://komarev.com/ghpvc/?username={GITHUB_USER}&style=flat-square")
    if resp is None:
        return "—"
    vals = re.findall(r">([^<]+)</text>", resp.text)
    return vals[-1].strip() if vals else "—"


def fetch_public_repos():
    resp = safe_get(f"https://api.github.com/users/{GITHUB_USER}")
    if resp is not None and resp.status_code == 200:
        return str(resp.json().get("public_repos", "—"))
    return "—"


def fetch_last_commit():
    resp = safe_get(
        f"https://api.github.com/repos/{GITHUB_USER}/{MAIN_PROJECT}/commits",
        params={"per_page": 1},
    )
    if resp is None or resp.status_code != 200:
        return "—"
    iso = resp.json()[0]["commit"]["committer"]["date"][:10]
    return date.fromisoformat(iso)

# ─── CARTE ACTIVITÉ (SVG auto-hébergé) ────────────────────────────────────────

FONT = "Segoe UI, Helvetica, Arial, sans-serif"
FLAME = ("M12,26 C12,26 7,22 7,17.5 C7,14 9.5,11.5 10.5,8.5 C12.5,11 13,13 12.8,15 "
         "C14.5,13.5 16,10.5 15.6,7 C18.5,10 20,13.5 20,17.5 C20,22 15,26 15,26 Z")


def build_activity_svg(streak, views, repos_count, last_commit):
    cols = []
    if streak:
        cols.append(("value", str(streak["total"]), "Total Contributions",
                     f'{streak["since"]:%b %d, %Y} - Present'))
        cols.append(("ring", str(streak["current"]), "Current Streak",
                     f'{streak["today"]:%b %d}'))
        cols.append(("value", str(streak["longest"]), "Longest Streak",
                     f'{streak["ls_start"]:%b %d} - {streak["ls_end"]:%b %d}'))
    cols.append(("value", views, "Profile Views", "all time"))
    cols.append(("value", repos_count, "Public Repos", "open source"))
    cols.append(("value", f'{last_commit:%b %d}' if last_commit != "—" else "—",
                 "Last Commit", MAIN_PROJECT))

    cw, h = 132, 150
    w = cw * len(cols)
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="GitHub activity card">',
        f'<rect width="{w}" height="{h}" rx="8" fill="#0C3038"/>',
    ]
    for i, (kind, value, label, sub) in enumerate(cols):
        cx = i * cw + cw // 2
        if i:
            p.append(f'<line x1="{i * cw}" y1="22" x2="{i * cw}" y2="{h - 22}" stroke="#247F82" stroke-width="1" opacity="0.6"/>')
        if kind == "ring":
            p.append(f'<circle cx="{cx}" cy="62" r="26" fill="none" stroke="#F2B544" stroke-width="3.5"/>')
            p.append(f'<path d="{FLAME}" fill="#D96852" transform="translate({cx - 13.5},30) scale(0.62)"/>')
            p.append(f'<text x="{cx}" y="70" text-anchor="middle" font-family="{FONT}" font-size="21" font-weight="700" fill="#FFFDF9">{xml_escape(value)}</text>')
        else:
            p.append(f'<text x="{cx}" y="70" text-anchor="middle" font-family="{FONT}" font-size="21" font-weight="700" fill="#FFFDF9">{xml_escape(value)}</text>')
        p.append(f'<text x="{cx}" y="96" text-anchor="middle" font-family="{FONT}" font-size="10.5" fill="#83C5BE">{xml_escape(label)}</text>')
        p.append(f'<text x="{cx}" y="116" text-anchor="middle" font-family="{FONT}" font-size="9" fill="#8A9C9A">{xml_escape(sub)}</text>')
    p.append("</svg>")
    return "\n".join(p)


def write_activity_svg():
    streak = fetch_streak_data()
    views = fetch_profile_views()
    repos_count = fetch_public_repos()
    last_commit = fetch_last_commit()

    if streak is None and views == "—":
        print("  ⚠️  Données d'activité indisponibles : SVG existant conservé.")
        return

    os.makedirs(os.path.dirname(ACTIVITY_SVG_PATH), exist_ok=True)
    with open(ACTIVITY_SVG_PATH, "w", encoding="utf-8") as f:
        f.write(build_activity_svg(streak, views, repos_count, last_commit))
    print(f"OK : {ACTIVITY_SVG_PATH} généré.")

# ─── INJECTION README ─────────────────────────────────────────────────────────

START_MARKER = "<!-- STACK:START -->"
END_MARKER = "<!-- STACK:END -->"


def inject_into_readme(readme_path, stack_md):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print(f"ERREUR : marqueurs absents dans {readme_path}.")
        return False

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    replacement = f"{START_MARKER}\n\n{stack_md}\n\n{END_MARKER}"
    new_content = pattern.sub(replacement, content)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("OK : README.md mis à jour.")
    return True

# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f"Scan des repos de @{GITHUB_USER}...")
    repos = get_repos(GITHUB_USER)
    print(f"  {len(repos)} repos publics trouvés.")

    all_techs = set()
    for repo in repos:
        techs = detect_from_repo(repo)
        if techs:
            print(f"  - {repo['name']}: {', '.join(sorted(techs))}")
        all_techs |= techs

    all_techs |= {"git", "github", "powerbi", "excel", "vscode", "sql"}

    print(f"\nTotal : {len(all_techs)} technologies détectées")
    inject_into_readme(README_PATH, generate_stack_markdown(all_techs))

    write_activity_svg()


if __name__ == "__main__":
    main()