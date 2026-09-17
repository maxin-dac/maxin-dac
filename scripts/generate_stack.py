#!/usr/bin/env python3
"""
README :
  Stack & Tools  -> badges shields.io <!-- STACK:START/END -->
"""

import json
import os
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GITHUB_USER = "maxin-dac"
README_PATH = "README.md"
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

# ─── BADGES STACK ─────────────────────────────────────────────────────────────
BADGE_MAP = {
    "python":        ("Python",         "3776AB", "python"),
    "sql":           ("SQL",            "4479A1", ""),
    "pandas":        ("Pandas",         "150458", "pandas"),
    "numpy":         ("NumPy",          "013243", ""),
    "plotly":        ("Plotly",         "3F4F75", "plotly"),
    "streamlit":     ("Streamlit",      "FF4B4B", "streamlit"),
    "powerbi":       ("Power BI",       "F2C811", "powerbi"),
    "excel":         ("Excel",          "217346", "microsoftexcel"),
    "git":           ("Git",            "F05032", "git"),
    "github":        ("GitHub",         "181717", "github"),
    "vscode":        ("VS Code",        "007ACC", "visualstudiocode"),
    "azure":         ("Azure",          "0078D4", "microsoftazure"),
    "copilot":       ("Copilot",        "000000", "githubcopilot"),
    "docker":        ("Docker",         "2496ED", "docker"),
    "fastapi":       ("FastAPI",        "009688", "fastapi"),
    "flask":         ("Flask",          "000000", "flask"),
    "django":        ("Django",         "092E20", "django"),
    "jupyter":       ("Jupyter",        "F37626", "jupyter"),
    "postgresql":    ("PostgreSQL",     "4169E1", "postgresql"),
    "mysql":         ("MySQL",          "4479A1", "mysql"),
    "mongodb":       ("MongoDB",        "47A248", "mongodb"),
    "scikit-learn":  ("scikit-learn",   "F7931E", "scikit-learn"),
    "pytorch":       ("PyTorch",        "EE4C2C", "pytorch"),
    "tensorflow":    ("TensorFlow",     "FF6F00", "tensorflow"),
    "javascript":    ("JavaScript",     "F7DF1E", "javascript"),
    "react":         ("React",          "61DAFB", "react"),
    "typescript":    ("TypeScript",     "3178C6", "typescript"),
    "nodejs":        ("Node.js",        "339933", "node.js"),
}

DISPLAY_ORDER = [
    "python", "sql", "pandas", "numpy", "plotly", "streamlit",
    "powerbi", "excel", "azure", "jupyter", "docker", "fastapi",
    "flask", "django", "postgresql", "mysql", "mongodb",
    "scikit-learn", "pytorch", "tensorflow", "javascript",
    "react", "typescript", "nodejs", "git", "github", "vscode",
    "copilot"
]

TECH_KEYWORDS = {
    "python": ["python", "pyproject", "requirements", "pipenv", "poetry", "conda"],
    "sql": ["sql", "sqlalchemy", "pyodbc", "pymssql", "psycopg", "postgresql", "postgres", "mysql", "sqlite", "duckdb", "snowflake"],
    "pandas": ["pandas", "dataframe", "pd."],
    "numpy": ["numpy", "np."],
    "plotly": ["plotly"],
    "streamlit": ["streamlit"],
    "powerbi": ["powerbi", "power bi", "dax"],
    "excel": ["excel", "xlsxwriter", "openpyxl", "pandas", "xlsx"],
    "azure": ["azure", "azure-functions", "azureml", "msfabric", "fabric", "mlflow"],
    "docker": ["docker", "dockerfile", "compose", "container"],
    "fastapi": ["fastapi", "uvicorn"],
    "flask": ["flask"],
    "django": ["django"],
    "jupyter": ["jupyter", "notebook", "ipython"],
    "postgresql": ["postgresql", "postgres", "psycopg"],
    "mysql": ["mysql"],
    "mongodb": ["mongodb", "pymongo"],
    "scikit-learn": ["scikit-learn", "sklearn", "xgboost", "lightgbm", "catboost"],
    "pytorch": ["torch", "pytorch"],
    "tensorflow": ["tensorflow", "keras"],
    "javascript": ["javascript", "node", "npm", "yarn", "express", "jest"],
    "react": ["react", "next", "vite", "jsx", "tsx"],
    "typescript": ["typescript", "tsconfig", "tsx"],
    "nodejs": ["node", "npm", "package.json", "express"],
}

LANG_ALIASES = {"shell": "bash", "javascript": "javascript", "typescript": "typescript", "python": "python", "jupyter notebook": "jupyter", "html": "javascript", "css": "javascript", "dockerfile": "docker"}

KNOWN_TECHS = set(BADGE_MAP) | set(TECH_KEYWORDS)

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


def get_repo_root_files(owner, repo):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents"
    resp = safe_get(url)
    if resp is None or resp.status_code != 200:
        return []
    try:
        payload = resp.json()
        if isinstance(payload, list):
            return [item.get("name", "").lower() for item in payload if item.get("name")]
    except (ValueError, TypeError):
        pass
    return []


def get_file_content(owner, repo, path):
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    resp = safe_get(url, raw=True)
    return resp.text if (resp is not None and resp.status_code == 200) else None


def detect_from_content(content):
    detected = set()
    text = (content or "").lower()
    for tech, keywords in TECH_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                detected.add(tech)
                break
    return detected


def parse_package_json(content):
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return set()
    deps = set()
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update((payload.get(section) or {}).keys())
    return {d.lower() for d in deps}

# ─── DETECTION STACK ──────────────────────────────────────────────────────────

def detect_from_repo(repo):
    detected = set()
    owner = repo["owner"]["login"]
    name = repo["name"]

    for lang in get_repo_languages(owner, name):
        key = LANG_ALIASES.get(lang.lower(), lang.lower())
        if key in KNOWN_TECHS:
            detected.add(key)

    root_files = set(get_repo_root_files(owner, name))
    files_to_check = [
        "requirements.txt", "pyproject.toml", "poetry.lock", "setup.py",
        "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
        "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        ".streamlit/config.toml", "environment.yml", "Pipfile", "requirements-dev.txt",
        "runtime.txt"
    ]

    for file_name in files_to_check:
        if file_name in root_files:
            content = get_file_content(owner, name, file_name)
            if file_name in {"package.json", "package-lock.json"}:
                detected |= detect_from_content("\n".join(parse_package_json(content or "")))
            else:
                detected |= detect_from_content(content or "")

    for path in ["requirements.txt", "pyproject.toml", ".streamlit/config.toml"]:
        content = get_file_content(owner, name, path)
        if content:
            detected |= detect_from_content(content)

    desc = (repo.get("description") or "").lower()
    if "dashboard" in desc or "data" in desc:
        detected.add("python")

    topics = {t.lower().replace("-", "") for t in repo.get("topics", [])}
    for topic in topics:
        if topic in KNOWN_TECHS:
            detected.add(topic)

    repo_name = name.lower()
    for token in ["streamlit", "plotly", "powerbi", "sql", "azure", "docker", "fastapi", "django", "flask", "jupyter"]:
        if token in repo_name:
            detected.add(token)

    return detected


def make_badge(label, color, logo):
    label_enc = label.replace(" ", "%20").replace("-", "--")
    if logo == "powerbi":
        logo_qs = "&logo=powerbi&logoColor=black"
    elif logo:
        logo_qs = f"&logo={logo}&logoColor=white"
    else:
        logo_qs = ""
    return f"![{label}](https://img.shields.io/badge/{label_enc}-{color}?style=flat-square{logo_qs})"


def generate_stack_markdown(all_techs):
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


if __name__ == "__main__":
    main()