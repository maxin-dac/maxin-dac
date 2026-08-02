#!/usr/bin/env python3
"""
Auto-génère la section "Stack & Tools" du README de profil.

Flux :
  1. Liste les repos publics via l'API GitHub
  2. Détecte les technos (langages, requirements.txt, pyproject.toml,
     .streamlit/config.toml, topics du repo)
  3. Construit une rangée d'icônes skillicons.dev
     (+ badges shields.io pour les outils BI sans icône skillicons)
  4. Injecte le résultat entre <!-- STACK:START --> et <!-- STACK:END -->

Usage :
  pip install requests
  python scripts/generate_stack.py                    # sans token : 60 req/h
  GITHUB_TOKEN=ghp_xxx python scripts/generate_stack.py
"""

import os
import re
import requests

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GITHUB_USER = "maxin-dac"
README_PATH = "README.md"
HYBRID_MODE = True   # True  = skillicons + badges shields pour outils BI
                     # False = 100% skillicons (Streamlit/Power BI/Excel masqués)
TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if TOKEN:
    HEADERS["Authorization"] = f"token {TOKEN}"

# ─── MAPPING TECH ─────────────────────────────────────────────────────────────
# techno détectée -> nom d'icône skillicons.dev (None = géré par le mode hybride)
SKILLICONS_MAP = {
    "python":     "python",
    "sql":        "sql",
    "pandas":     "pandas",
    "numpy":      "numpy",
    "plotly":     "plotly",
    "sklearn":    "sklearn",
    "git":        "git",
    "github":     "github",
    "vscode":     "vscode",
    "bash":       "bash",
    "linux":      "linux",
    "docker":     "docker",
    "azure":      "azure",
    "postgres":   "postgres",
    "mysql":      "mysql",
    "mongodb":    "mongodb",
    "r":          "r",
    "tensorflow": "tensorflow",
    "pytorch":    "pytorch",
    "fastapi":    "fastapi",
    "flask":      "flask",
    "django":     "django",
    "react":      "react",
    "js":         "js",
    "ts":         "ts",
    "html":       "html",
    "css":        "css",
    # Pas d'icône skillicons -> badges hybrides uniquement
    "streamlit":  None,
    "powerbi":    None,
    "excel":      None,
    "copilot":    None,
    "fabric":     None,
    "matplotlib": None,
    "seaborn":    None,
    "scipy":      None,
    "openai":     None,
    "langchain":  None,
}

# Ordre d'affichage de la rangée d'icônes (gauche -> droite)
ICON_ORDER = [
    "python", "sql", "pandas", "numpy", "plotly", "sklearn",
    "git", "github", "vscode", "bash", "linux", "docker",
    "azure", "postgres", "mysql", "mongodb", "r",
    "tensorflow", "pytorch", "fastapi", "flask", "django",
    "react", "js", "ts", "html", "css",
]

# Alias : nom de langage GitHub -> clé de détection
LANG_ALIASES = {
    "shell": "bash",
    "javascript": "js",
    "typescript": "ts",
}

# Badges shields.io de secours pour les outils BI (mode hybride)
HYBRID_BADGES = {
    "streamlit": ("Streamlit", "FF4B4B", "streamlit"),
    "powerbi":   ("Power BI", "F2C811", "powerbi"),
    "excel":     ("Excel", "217346", "microsoftexcel"),
    "fabric":    ("Microsoft Fabric", "0078D4", "microsoft"),
    "copilot":   ("GitHub Copilot", "000000", "githubcopilot"),
}
HYBRID_ORDER = ["streamlit", "powerbi", "excel", "fabric", "copilot"]

# Mots-clés cherchés dans requirements.txt / pyproject.toml
REQ_KEYWORDS = {
    "streamlit":  ["streamlit"],
    "plotly":     ["plotly"],
    "pandas":     ["pandas"],
    "numpy":      ["numpy"],
    "scipy":      ["scipy"],
    "sklearn":    ["scikit-learn", "sklearn"],
    "matplotlib": ["matplotlib"],
    "seaborn":    ["seaborn"],
    "openai":     ["openai"],
    "langchain":  ["langchain"],
    "azure":      ["azure"],
    "fastapi":    ["fastapi"],
    "flask":      ["flask"],
    "django":     ["django"],
    "sql":        ["sqlalchemy", "pyodbc", "pymssql", "psycopg"],
}

# ─── API GITHUB ───────────────────────────────────────────────────────────────

def get_repos(username):
    url = f"https://api.github.com/users/{username}/repos"
    params = {"per_page": 100, "sort": "updated", "type": "public"}
    resp = requests.get(url, headers=HEADERS, params=params)
    resp.raise_for_status()
    repos = resp.json()
    return [r for r in repos if not r["fork"] and not r["archived"]]


def get_repo_languages(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    resp = requests.get(url, headers=HEADERS)
    return resp.json() if resp.status_code == 200 else {}


def get_file_content(owner, repo, path):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    headers = {**HEADERS, "Accept": "application/vnd.github.v3.raw"}
    resp = requests.get(url, headers=headers)
    return resp.text if resp.status_code == 200 else None


# ─── DÉTECTION ────────────────────────────────────────────────────────────────

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

    # 1. Langages GitHub
    langs = get_repo_languages(owner, name)
    for lang in langs:
        key = LANG_ALIASES.get(lang.lower(), lang.lower())
        if key in SKILLICONS_MAP:
            detected.add(key)

    # 2. requirements.txt
    req = get_file_content(owner, name, "requirements.txt")
    if req:
        detected |= detect_from_requirements(req)

    # 3. pyproject.toml (fallback)
    if not req:
        pyproject = get_file_content(owner, name, "pyproject.toml")
        if pyproject:
            detected |= detect_from_requirements(pyproject)

    # 4. .streamlit/config.toml -> Streamlit
    if get_file_content(owner, name, ".streamlit/config.toml"):
        detected.add("streamlit")

    # 5. Topics du repo (ex: "power-bi", "azure")
    for topic in repo.get("topics", []):
        t = topic.lower().replace("-", "")
        if t in SKILLICONS_MAP:
            detected.add(t)

    return detected


# ─── GÉNÉRATION ───────────────────────────────────────────────────────────────

def make_shields_badge(label, color, logo):
    label_enc = label.replace(" ", "%20").replace("-", "--")
    return f"![{label}](https://img.shields.io/badge/{label_enc}-{color}?style=flat&logo={logo}&logoColor=white)"


def generate_stack_markdown(all_techs):
    parts = []

    # 1. Rangée d'icônes skillicons
    icons = [SKILLICONS_MAP[t] for t in ICON_ORDER
             if t in all_techs and SKILLICONS_MAP.get(t)]
    if icons:
        url = "https://skillicons.dev/icons?i=" + ",".join(icons) + "&theme=dark"
        parts.append(f'<img src="{url}" alt="Tech stack" />')

    # 2. Badges hybrides pour les outils BI (pas d'icône skillicons)
    if HYBRID_MODE:
        extras = [make_shields_badge(*HYBRID_BADGES[t])
                  for t in HYBRID_ORDER if t in all_techs]
        if extras:
            parts.append(" ".join(extras))

    if not parts:
        return "_Stack auto-détecté : aucun repo public pour l'instant._"

    return "\n\n".join(parts)


# ─── INJECTION README ─────────────────────────────────────────────────────────

START_MARKER = "<!-- STACK:START -->"
END_MARKER = "<!-- STACK:END -->"


def inject_into_readme(readme_path, stack_md):
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print(f"ERREUR : marqueurs absents dans {readme_path}.")
        print(f"Ajoute ces deux lignes autour de la section Stack :")
        print(f"  {START_MARKER}")
        print(f"  {END_MARKER}")
        return False

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    replacement = f"{START_MARKER}\n\n{stack_md}\n\n{END_MARKER}"
    new_content = pattern.sub(replacement, content)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"OK : README.md mis à jour.")
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

    # Outils toujours présents (non détectables dans le code)
    all_techs |= {"git", "github", "powerbi", "excel"}

    print(f"\nTotal : {len(all_techs)} technologies détectées")
    stack_md = generate_stack_markdown(all_techs)
    inject_into_readme(README_PATH, stack_md)


if __name__ == "__main__":
    main()