#!/usr/bin/env python3
"""
push_to_github.py — Создаёт репозиторий на GitHub и заливает весь проект.

Заполни три переменные ниже и запусти:
  python push_to_github.py
"""

import os
import subprocess
import urllib.request
import urllib.error
import json

# ─── ЗАПОЛНИ ЭТИ ПОЛЯ ────────────────────────────────────────────────────────
GITHUB_USERNAME  = ""          # твой GitHub логин
GITHUB_TOKEN     = ""          # Personal Access Token (права: repo)
REPO_NAME        = "vpn-manager"
REPO_DESCRIPTION = "CLI tool for collecting, testing and connecting proxy servers on Windows"
REPO_PRIVATE     = False       # True = приватный репозиторий
# ─────────────────────────────────────────────────────────────────────────────

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; C = "\033[96m"
B = "\033[1m";  RS = "\033[0m"; DIM = "\033[2m"

def run(cmd, cwd=None, check=True):
    result = subprocess.run(cmd, shell=True, cwd=cwd,
                            capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"  {R}Ошибка: {result.stderr.strip()}{RS}")
        raise SystemExit(1)
    return result.stdout.strip()

def api(method, endpoint, data=None):
    url = f"https://api.github.com{endpoint}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def main():
    print(f"\n{C}{B}╔══════════════════════════════════════════════╗")
    print(f"║   GitHub Publisher — VPN/Proxy Manager       ║")
    print(f"╚══════════════════════════════════════════════╝{RS}\n")

    # Валидация
    if not GITHUB_USERNAME or not GITHUB_TOKEN:
        print(f"  {R}Заполни GITHUB_USERNAME и GITHUB_TOKEN в файле!{RS}")
        raise SystemExit(1)

    repo_dir = os.path.dirname(os.path.abspath(__file__))

    # ── 1. Создание репозитория ───────────────────────────────
    print(f"  {B}[1/4] Создание репозитория {REPO_NAME}…{RS}")
    resp, status = api("POST", "/user/repos", {
        "name":        REPO_NAME,
        "description": REPO_DESCRIPTION,
        "private":     REPO_PRIVATE,
        "auto_init":   False,
    })
    if status == 201:
        clone_url = resp["clone_url"]
        html_url  = resp["html_url"]
        print(f"  {G}✔ Репозиторий создан: {html_url}{RS}")
    elif status == 422:
        print(f"  {Y}Репозиторий уже существует — используем его.{RS}")
        clone_url = f"https://github.com/{GITHUB_USERNAME}/{REPO_NAME}.git"
        html_url  = f"https://github.com/{GITHUB_USERNAME}/{REPO_NAME}"
    else:
        print(f"  {R}Ошибка API ({status}): {resp}{RS}")
        raise SystemExit(1)

    # Добавляем токен в URL для авторизации push
    auth_url = clone_url.replace("https://", f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@")

    # ── 2. Git init ───────────────────────────────────────────
    print(f"\n  {B}[2/4] Инициализация git…{RS}")
    git = f"git -C {repo_dir}"

    if not os.path.exists(os.path.join(repo_dir, ".git")):
        run(f"{git} init")
        print(f"  {G}✔ git init{RS}")
    else:
        print(f"  {DIM}git уже инициализирован{RS}")

    run(f'{git} config user.email "{GITHUB_USERNAME}@users.noreply.github.com"')
    run(f'{git} config user.name "{GITHUB_USERNAME}"')

    # ── 3. Коммит ─────────────────────────────────────────────
    print(f"\n  {B}[3/4] Коммит файлов…{RS}")
    run(f"{git} add -A")

    # Проверяем есть ли что коммитить
    status_out = run(f"{git} status --porcelain", check=False)
    if status_out:
        run(f'{git} commit -m "feat: initial release v1.2.0\n\n'
            f'- Module 1: proxy collector (HTML/file/API + TTL cache)\n'
            f'- Module 2: speed tester (batches, parallel, fail eviction)\n'
            f'- Module 3: Windows proxy connector (winreg + PS + netsh)\n'
            f'- dist/: setup.bat + build_exe_source.py\n'
            f'- AI_HINTS.md for each module\n'
            f'- CHANGELOG.md + DEVLOG.md"')
        print(f"  {G}✔ Коммит создан{RS}")
    else:
        print(f"  {DIM}Нечего коммитить — всё уже закоммичено{RS}")

    # ── 4. Push ───────────────────────────────────────────────
    print(f"\n  {B}[4/4] Push на GitHub…{RS}")

    # Устанавливаем remote
    remotes = run(f"{git} remote", check=False)
    if "origin" in remotes.split():
        run(f"{git} remote set-url origin {auth_url}")
    else:
        run(f"{git} remote add origin {auth_url}")

    # Переименовываем ветку в main если нужно
    run(f"{git} branch -M main", check=False)
    run(f"{git} push -u origin main --force")

    print(f"\n  {G}{B}✔ Готово!{RS}")
    print(f"\n  {C}Репозиторий: {html_url}{RS}")
    print(f"  {DIM}Клонировать: git clone {clone_url}{RS}\n")

if __name__ == "__main__":
    main()
