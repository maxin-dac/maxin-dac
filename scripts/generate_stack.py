#!/usr/bin/env python3
import os
import re
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GITHUB_USER = "maxin-dac"
README_PATH = "README.md"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
TIMEOUT = 15  # secondes par requête

session = requests.Session()
retries = Retry(
    total=5,
    backoff_factor=1.5,                        # 1.5s, 3s, 6s, 12s, 24s
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

LANG_ALIASES = {
    "shell": "bash",
    "javascript": "js",
    "typescript": "ts",
}

KNOWN_TECHS = set(BADGE_MAP) | set(REQ_KEYWORDS)

# ─── API GITHUB ───────────────────────────────────────────────────────────────

def safe_get(url, params=None, raw=False):
    """GET robuste avec retries + gestion d'erreur lisible."""
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
        raise SystemExit(
            f"❌ Impossible de récupérer les repos (status: {status}).\n"
            f"   403 -> rate limit : configure GITHUB_TOKEN.\n"
            f"   'aucune réponse' -> réseau : proxy / VPN / antivirus."
        )
    repos = resp.json()
    return [r for r in repos if not r["fork"] and not r["archived"]]

def get_repo_languages(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    resp = safe_get(url)
    if resp is not None and resp.status_code == 200:
        return resp.json()
    return {}

def get_file_content(owner, repo, path):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    resp = safe_get(url, raw=True)
    if resp is not None and resp.status_code == 200:
        return resp.text
    return None

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

    langs = get_repo_languages(owner, name)
    for lang in langs:
        key = LANG_ALIASES.get(lang.lower(), lang.lower())
        if key in KNOWN_TECHS:
            detected.add(key)

    req = get_file_content(owner, name, "requirements.txt")
    if req:
        detected |= detect_from_requirements(req)

    if not req:
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
    """Badge shields.io 'for-the-badge' uniforme."""
    label_enc = label.replace(" ", "%20").replace("-", "--")
    if logo == "powerbi":                       # fond jaune -> logo noir
        logo_qs = "&logo=powerbi&logoColor=black"
    elif logo:
        logo_qs = f"&logo={logo}&logoColor=white"
    else:
        logo_qs = ""                            # SQL / NumPy : texte seul
    return f"![{label}](https://img.shields.io/badge/{label_enc}-{color}?style=for-the-badge{logo_qs})"

def generate_stack_markdown(all_techs):
    """Une seule rangée de badges, dans l'ordre DISPLAY_ORDER."""
    badges = [make_badge(*BADGE_MAP[t]) for t in DISPLAY_ORDER if t in all_techs]
    if not badges:
        return "_Stack auto-détecté : aucun repo public pour l'instant._"
    return " ".join(badges)

# ─── INJECTION README ─────────────────────────────────────────────────────────

START_MARKER = "<!-- STACK:START -->"
END_MARKER = "<!-- STACK:END -->"

def inject_into_readme(readme_path, stack_md):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print(f"ERREUR : marqueurs absents dans {readme_path}.")
        print(f"  Ajoute : {START_MARKER}  et  {END_MARKER}")
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

if __name__ == "__main__":
    main()
