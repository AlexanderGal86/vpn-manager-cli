#!/usr/bin/env python3
"""
push_to_github.py
=================
Run this script to create the GitHub repo and push all files.
Fill in GITHUB_TOKEN below and run: python push_to_github.py
"""

import os, sys, subprocess, json, getpass
import urllib.request, urllib.error

USERNAME  = "AlexanderGal86"
REPO_NAME = "vpn-manager-cli"
REPO_DESC = "CLI tool for collecting, testing and connecting proxy servers on Windows"
PRIVATE   = False

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

G="\033[92m";Y="\033[93m";R="\033[91m";C="\033[96m";B="\033[1m";RS="\033[0m";DIM="\033[2m"

def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"  {R}Error:{RS} {r.stderr.strip() or r.stdout.strip()}")
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
    print(f"\n{C}{B}+=============================================+")
    print(f"  VPN/Proxy Manager - GitHub Deploy Script")
    print(f"+=============================================+{RS}")
    print(f"  Username:   {C}{USERNAME}{RS}")
    print(f"  Repository: {C}{REPO_NAME}{RS}\n")

    print(f"  Enter your GitHub Personal Access Token")
    print(f"  {DIM}(github.com/settings/tokens -> Generate new token classic -> repo){RS}")
    token = getpass.getpass("  Token: ").strip()
    if not token:
        print(f"  {R}No token entered.{RS}"); sys.exit(1)

    print(f"\n  {DIM}Verifying token...{RS}", end="", flush=True)
    resp, code = api("GET", "/user", token)
    if code != 200:
        print(f"\r  {R}Invalid token (HTTP {code}){RS}"); sys.exit(1)
    print(f"\r  {G}Authorized as: {resp['login']}{RS}")

    print(f"\n  {B}[1/4]{RS} Creating repository...")
    resp, code = api("POST", "/user/repos", token, {
        "name": REPO_NAME, "description": REPO_DESC,
        "private": PRIVATE, "auto_init": False,
    })
    if code == 201:
        html_url = resp["html_url"]
        print(f"  {G}Created: {html_url}{RS}")
    elif code == 422:
        html_url = f"https://github.com/{USERNAME}/{REPO_NAME}"
        print(f"  {Y}Repository already exists - using it{RS}")
    else:
        print(f"  {R}API error {code}: {resp}{RS}"); sys.exit(1)

    auth_url = f"https://{USERNAME}:{token}@github.com/{USERNAME}/{REPO_NAME}.git"
    repo_dir = os.path.dirname(os.path.abspath(__file__))

    print(f"\n  {B}[2/4]{RS} Initializing git...")
    git = f"git -C \"{repo_dir}\""
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        run(f"{git} init")
    run(f'{git} config user.name "{USERNAME}"')
    run(f'{git} config user.email "{USERNAME}@users.noreply.github.com"')
    print(f"  {G}OK{RS}")

    print(f"\n  {B}[3/4]{RS} Committing files...")
    run(f"{git} add -A")
    status_out = run(f"{git} status --porcelain", check=False)
    if status_out:
        run(f'{git} commit -m "feat: full release v1.2.0 - all encoding fixes applied"')
        print(f"  {G}Committed{RS}")
    else:
        print(f"  {DIM}Nothing to commit{RS}")

    print(f"\n  {B}[4/4]{RS} Pushing to GitHub...")
    remotes = run(f"{git} remote", check=False)
    if "origin" in remotes.split():
        run(f"{git} remote set-url origin {auth_url}")
    else:
        run(f"{git} remote add origin {auth_url}")
    run(f"{git} branch -M main", check=False)
    run(f"{git} push -u origin main --force")

    print(f"\n  {G}{B}Done!{RS}")
    print(f"  {C}{html_url}{RS}\n")

if __name__ == "__main__":
    main()
