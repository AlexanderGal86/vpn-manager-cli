#!/usr/bin/env python3
"""
deploy_to_github.py
===================
Запусти этот скрипт на СВОЕЙ машине (Windows/Mac/Linux).
Он создаст репозиторий на GitHub и загрузит весь проект.

Требования: Python 3.6+, git установлен и доступен в PATH
"""

import os, sys, subprocess, json, getpass
import urllib.request, urllib.error

USERNAME  = "AlexanderGal86"
REPO_NAME = "vpn-manager-cli"
REPO_DESC = "CLI tool for collecting, testing and connecting proxy servers on Windows"
PRIVATE   = False

G="\033[92m";Y="\033[93m";R="\033[91m";C="\033[96m";B="\033[1m";RS="\033[0m";DIM="\033[2m"

if sys.platform=="win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(ctypes.windll.kernel32.GetStdHandle(-11),7)
    except: pass

def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"  {R}Ошибка:{RS} {r.stderr.strip() or r.stdout.strip()}")
        sys.exit(1)
    return r.stdout.strip()

def api(method, endpoint, token, data=None):
    url = f"https://api.github.com{endpoint}"
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"token {token}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
        "User-Agent":    "vpn-manager-deploy",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read()), r.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code

def main():
    print(f"""
{C}{B}╔════════════════════════════════════════════════════╗
║   VPN/Proxy Manager — GitHub Deploy Script         ║
╚════════════════════════════════════════════════════╝{RS}
  Username:    {C}{USERNAME}{RS}
  Repository:  {C}{REPO_NAME}{RS}
""")

    # Запрашиваем токен
    print(f"  Введи GitHub Personal Access Token")
    print(f"  {DIM}(github.com/settings/tokens → Generate new token classic → галочка repo){RS}")
    token = getpass.getpass("  Token: ").strip()
    if not token:
        print(f"  {R}Токен не введён.{RS}"); sys.exit(1)

    # Проверка токена
    print(f"\n  {DIM}Проверка токена…{RS}", end="", flush=True)
    resp, code = api("GET", "/user", token)
    if code != 200:
        print(f"\r  {R}✖ Неверный токен (HTTP {code}){RS}"); sys.exit(1)
    print(f"\r  {G}✔ Авторизован как: {resp['login']}{RS}")

    # Создание репозитория
    print(f"\n  {B}[1/4]{RS} Создание репозитория…")
    resp, code = api("POST", "/user/repos", token, {
        "name": REPO_NAME, "description": REPO_DESC,
        "private": PRIVATE, "auto_init": False,
    })
    if code == 201:
        html_url = resp["html_url"]
        print(f"  {G}✔ Создан: {html_url}{RS}")
    elif code == 422:
        html_url = f"https://github.com/{USERNAME}/{REPO_NAME}"
        print(f"  {Y}Репозиторий уже существует — используем его{RS}")
    else:
        print(f"  {R}✖ Ошибка API {code}: {resp}{RS}"); sys.exit(1)

    auth_url = f"https://{USERNAME}:{token}@github.com/{USERNAME}/{REPO_NAME}.git"
    bundle   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vpn-manager-cli.bundle")
    work_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_deploy_tmp")

    # Распаковка бандла
    print(f"\n  {B}[2/4]{RS} Распаковка git bundle…")
    if not os.path.exists(bundle):
        print(f"  {R}✖ Файл не найден: {bundle}{RS}"); sys.exit(1)
    os.makedirs(work_dir, exist_ok=True)
    run(f"git clone {bundle} .", cwd=work_dir)
    run(f"git config user.name \"{USERNAME}\"", cwd=work_dir)
    run(f"git config user.email \"{USERNAME}@users.noreply.github.com\"", cwd=work_dir)
    print(f"  {G}✔ Репозиторий распакован{RS}")

    # Remote + push
    print(f"\n  {B}[3/4]{RS} Настройка remote…")
    run(f"git remote set-url origin {auth_url}", cwd=work_dir, check=False)
    run(f"git remote add origin {auth_url}",     cwd=work_dir, check=False)
    print(f"  {G}✔ Remote установлен{RS}")

    print(f"\n  {B}[4/4]{RS} Push на GitHub…")
    run(f"git push -u origin main --force", cwd=work_dir)
    print(f"  {G}✔ Push выполнен{RS}")

    # Очистка
    import shutil; shutil.rmtree(work_dir, ignore_errors=True)

    print(f"""
  {G}{B}═══════════════════════════════════════{RS}
  {G}✔  Готово!{RS}
  {C}  {html_url}{RS}
  {G}{B}═══════════════════════════════════════{RS}
""")

if __name__ == "__main__":
    main()
