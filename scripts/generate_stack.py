#!/usr/bin/env python3

import os
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from xml.sax.saxutils import escape as xml_escape

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GITHUB_USER = "maxin-dac"
README_PATH = "README.md"
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

# ─── BADGES ──────────────────────────────────────────────────
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

# ─── DETECTION ────────────────────────────────────────────────────────────────

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

# ─── GENERATION ───────────────────────────────────────────────────────────────

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

# ─── TOP LANGUAGES (SVG auto-hébergé) ─────────────────────────────────────────

TOP_LANGS_PATH = "assets/top-languages.svg"
EXCLUDE_LANGS = {"HTML", "CSS", "Shell", "Dockerfile", "SCSS", "Makefile"}
PALETTE = ["#F2B544", "#83C5BE", "#D96852", "#247F82", "#F9D276", "#F6A18A"]
FONT = "Segoe UI, Helvetica, Arial, sans-serif"


def fetch_top_languages(owner, repos, top_n=6):
    """Agrège les octets par langage sur tous les repos -> [(lang, pct)]."""
    totals = {}
    for repo in repos:
        for lang, nbytes in get_repo_languages(owner, repo["name"]).items():
            if lang in EXCLUDE_LANGS:
                continue
            totals[lang] = totals.get(lang, 0) + nbytes
    total = sum(totals.values())
    if total == 0:
        return []
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [(lang, 100.0 * nbytes / total) for lang, nbytes in ranked]


def build_top_langs_svg(rows):
    """Carte 'Top Languages' aux couleurs du portfolio (fond teal-900)."""
    w, pad, row_h, title_h = 340, 18, 34, 46
    h = title_h + len(rows) * row_h + pad
    bar_w = w - 2 * pad
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="Top languages">',
        f'<rect width="{w}" height="{h}" rx="10" fill="#0C3038"/>',
        f'<text x="{pad}" y="28" font-family="{FONT}" font-size="15" font-weight="700" fill="#F2B544">Top Languages</text>',
        f'<rect x="{pad}" y="36" width="52" height="3" rx="1.5" fill="#F2B544"/>',
    ]
    y = title_h + 14
    for i, (lang, pct) in enumerate(rows):
        color = PALETTE[i % len(PALETTE)]
        p.append(f'<text x="{pad}" y="{y}" font-family="{FONT}" font-size="12.5" fill="#FFFDF9">{xml_escape(lang)}</text>')
        p.append(f'<text x="{w - pad}" y="{y}" text-anchor="end" font-family="{FONT}" font-size="12.5" fill="#83C5BE">{pct:.1f}%</text>')
        p.append(f'<rect x="{pad}" y="{y + 8}" width="{bar_w}" height="6" rx="3" fill="#124D55"/>')
        p.append(f'<rect x="{pad}" y="{y + 8}" width="{max(6.0, bar_w * pct / 100):.1f}" height="6" rx="3" fill="{color}"/>')
        y += row_h
    p.append("</svg>")
    return "\n".join(p)


def write_top_langs_svg(owner, repos):
    """Génère le SVG top-languages dans assets/top-languages.svg."""
    rows = fetch_top_languages(owner, repos)
    if not rows:
        print("  ⚠️  Aucun langage agrégé, SVG non généré.")
        return
    os.makedirs(os.path.dirname(TOP_LANGS_PATH), exist_ok=True)
    with open(TOP_LANGS_PATH, "w", encoding="utf-8") as f:
        f.write(build_top_langs_svg(rows))
    print(f"OK : {TOP_LANGS_PATH} généré ({', '.join(l for l, _ in rows)}).")

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
    stack_md = generate_stack_markdown(all_techs)
    inject_into_readme(README_PATH, stack_md)
    
    # Génération du SVG top-languages
    write_top_langs_svg(GITHUB_USER, repos)

if __name__ == "__main__":
    main()