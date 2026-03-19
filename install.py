#!/usr/bin/env python3
"""
VPN / PROXY MANAGER — Self-Extracting Archive
Run: python install.py
"""
import os, sys, zipfile, base64, io, subprocess

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

ARCHIVE_B64 = (
    "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"
    "AAAQAO1BAAAAAHZwbi1tYW5hZ2VyL1VUBQADBMy7aXV4CwABBAAAAAAEAAAAAFBLAQIeAwoAAAAAAAB+"
    "clwAAAAAAAAAAAAAAAAeABgAAAAAAAAAEADtQUIAAAB2cG4tbWFuYWdlci9tb2R1bGUzX2Nvbm5lY3Rv"
    "ci9VVAUAAzDJuml1eAsAAQQAAAAABAAAAABQSwECHgMKAAAAAACifXJcAAAAAAAAAAAAAAAAJQAYAAAA"
    "AAAAABAA7UGWAAAAdnBuLW1hbmFnZXIvbW9kdWxlM19jb25uZWN0b3Ivb3V0cHV0L1VUBQADf8i6aXV4"
    "CwABBAAAAAAEAAAAAFBLAQIeAxQAAAAIAOtDc1wu7Tz+gQ8AAPs1AAAqABgAAAAAAAEAAACkgfEAAAB2"
    "cG4tbWFuYWdlci9tb2R1bGUzX2Nvbm5lY3Rvci9jb25uZWN0b3IucHlVVAUAA1q0u2l1eAsAAQQAAAAA"
    "BAAAAABQSwECHgMKAAAAAACvgHJcAAAAAAAAAAAAAAAAGwAYAAAAAAAAABAA7UHSEAAAdnBuLW1hbmFn"
    "ZXIvbW9kdWxlMl90ZXN0ZXIvVVQFAANJzbppdXgLAAEEAAAAAAQAAAAAUEsBAh4DFAAAAAgA3ENzXAA6"
    "3z/TFQAAkUgAACQAGAAAAAAAAQAAAKSBIxEAAHZwbi1tYW5hZ2VyL21vZHVsZTJfdGVzdGVyL3Rlc3Rl"
    "ci5weVVUBQADP7S7aXV4CwABBAAAAAAEAAAAAFBLAQIeAwoAAAAAAKJ9clwAAAAAAAAAAAAAAAAiABgA"
    "AAAAAAAAEADtQVAnAAB2cG4tbWFuYWdlci9tb2R1bGUyX3Rlc3Rlci9vdXRwdXQvVVQFAAN/yLppdXgL"
    "AAEEAAAAAAQAAAAAUEsBAh4DFAAAAAgAwkJzXBMJU6w/AAAAQwAAABwAGAAAAAAAAQAAAKSBqCcAAHZw"
    "bi1tYW5hZ2VyL3JlcXVpcmVtZW50cy50eHRVVAUAAyyyu2l1eAsAAQQAAAAABAAAAABQSwECHgMKAAAA"
    "AACvgHJcAAAAAAAAAAAAAAAAHgAYAAAAAAAAABAA7UE5KAAAdnBuLW1hbmFnZXIvbW9kdWxlMV9jb2xs"
    "ZWN0b3IvVVQFAANJzbppdXgLAAEEAAAAAAQAAAAAUEsBAh4DFAAAAAgA3ENzXCWtOerRFgAAyVEAACoA"
    "GAAAAAAAAQAAAKSBjSgAAHZwbi1tYW5hZ2VyL21vZHVsZTFfY29sbGVjdG9yL2NvbGxlY3Rvci5weVVU"
    "BQADP7S7aXV4CwABBAAAAAAEAAAAAFBLAQIeAwoAAAAAAKJ9clwAAAAAAAAAAAAAAAAlABgAAAAAAAAA"
    "EADtQb4/AAB2cG4tbWFuYWdlci9tb2R1bGUxX2NvbGxlY3Rvci9vdXRwdXQvVVQFAAN/yLppdXgLAAEE"
    "AAAAAAQAAAAAUEsBAh4DFAAAAAgAHX5yXJwpjL62CAAAbBQAABUAGAAAAAAAAQAAAKSBGUAAAHZwbi1t"
    "YW5hZ2VyL1JFQURNRS5tZFVUBQADasm6aXV4CwABBAAAAAAEAAAAAFBLAQIeAxQAAAAIANxDc1x/gxPX"
    "kAcAADAZAAATABgAAAAAAAEAAACkgRpJAAB2cG4tbWFuYWdlci9tYWluLnB5VVQFAAM/tLtpdXgLAAEE"
    "AAAAAAQAAAAAUEsBAh4DFAAAAAgAilFzXKXrtPHZCAAAYB8AABsAGAAAAAAAAQAAAKSB81AAAHZwbi1t"
    "YW5hZ2VyL3Zwbl9tYW5hZ2VyLnBzMVVUBQADBMy7aXV4CwABBAAAAAAEAAAAAFBLAQIeAxQAAAAIAIpR"
    "c1xNqZdDyQAAAP0AAAAbABgAAAAAAAEAAACkgR1aAAB2cG4tbWFuYWdlci92cG5fbWFuYWdlci5iYXRV"
    "VAUAAwTMu2l1eAsAAQQAAAAABAAAAABQSwECFAMUAAAACAABbXNc07KEN1QAAABTAAAAEwAAAAAAAAAA"
    "AAAAgAE3WwAAdnBuLW1hbmFnZXIvcnVuLmJhdFBLBQYAAAAAEAAQABwGAAC8WwAAAAA="
)

def banner():
    print(f"""
{C}{B}+=============================================================+
|   VPN / PROXY MANAGER  -  Installer                        |
+=============================================================+{RS}
""")

def progress_bar(done, total, width=36):
    filled = int(width * done / max(total, 1))
    bar = f"{G}{'#' * filled}{DIM}{'-' * (width - filled)}{RS}"
    return f"[{bar}] {done/total*100:5.1f}%"

def extract():
    banner()
    print(f"  {C}Decoding archive...{RS}")
    raw  = base64.b64decode(ARCHIVE_B64)
    zf   = zipfile.ZipFile(io.BytesIO(raw))
    names = [n for n in zf.namelist() if "__pycache__" not in n]
    total = len(names)
    dest  = os.path.abspath("vpn-manager")
    if os.path.exists(dest):
        print(f"\n  {Y}Folder exists: {dest}{RS}")
        if input("  Overwrite? [y/N] > ").strip().lower() != "y":
            print(f"  {Y}Cancelled.{RS}\n"); return False
    print(f"\n  {B}Extracting to {dest}{RS}\n")
    done = 0
    for name in names:
        if name.endswith("/"): done += 1; continue
        target = os.path.join(os.path.abspath("."), name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with zf.open(name) as src, open(target, "wb") as dst:
            dst.write(src.read())
        done += 1
        short = name[len("vpn-manager/"):]
        print(f"  {progress_bar(done, total)}  {DIM}{short[:45]:<45}{RS}", end="\r", flush=True)
    print(f"  {progress_bar(total, total)}  {G}Done!{RS}              ")
    print(f"\n  {G}Extracted {total} files to:\n    {C}{dest}{RS}")
    return True

def install_deps():
    req = os.path.join("vpn-manager", "requirements.txt")
    print(f"\n  {B}Install Python dependencies{RS}")
    print(f"  {DIM}requests, beautifulsoup4, lxml, PySocks{RS}\n")
    if input("  Install now? [Y/n] > ").strip().lower() in ("", "y"):
        print()
        # Run pip WITHOUT -q so errors are visible
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", req],
        )
        print()
        if result.returncode == 0:
            # Verify the key package actually imports
            try:
                import importlib
                importlib.import_module("requests")
                print(f"  {G}Dependencies installed and verified.{RS}")
            except ImportError:
                print(f"  {Y}pip reported success but 'requests' is not importable.")
                print(f"  Try: pip install -r {req}{RS}")
        else:
            print(f"  {R}pip failed (exit code {result.returncode}).{RS}")
            print(f"  Run manually:  pip install -r {req}")
            print(f"  Or:            python -m pip install -r {req}")
    else:
        print(f"\n  {Y}Skipped. Run before starting:{RS}")
        print(f"    pip install -r {req}")

def show_usage():
    print(f"""
{C}{B}  -----------------------------------------------------------{RS}
  {B}How to run:{RS}
    {C}cd vpn-manager{RS}
    {G}python main.py{RS}              # full pipeline: 1 -> 2 -> 3
    {G}python main.py --module 1{RS}   # collect proxies only
    {G}python main.py --module 2{RS}   # speed test only
    {G}python main.py --module 3{RS}   # connect only

  {B}Output files:{RS}
    {DIM}module1_collector/output/proxy_list.json{RS}
    {DIM}module2_tester/output/viable_proxies.json{RS}
    {DIM}module3_connector/output/connection_log.txt{RS}

  {B}Module 3 requires admin rights{RS} {DIM}(registry write){RS}
{C}{B}  -----------------------------------------------------------{RS}
""")

if __name__ == "__main__":
    ok = extract()
    if ok:
        install_deps()
        show_usage()
    input(f"  {DIM}[Enter] to exit...{RS}")
