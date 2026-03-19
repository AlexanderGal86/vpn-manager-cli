# VPN / Proxy Manager

> CLI tool for automatic proxy collection, speed testing, and system-level connection on Windows.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2B-informational?logo=windows)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What it does

Three independent CLI modules connected in a pipeline:

```
[Module 1: Collector] --proxy_list.json--> [Module 2: Tester] --viable_proxies.json--> [Module 3: Connector]
   Collect IPs from                          Speed test in                                 Set Windows
   open sources:                             batches of 10,                               system proxy via
   HTML / files / API                        2 in parallel,                               registry + netsh
                                             TTL cache
```

---

## Quick start

### Option A — BAT installer (Python required)
```
Download dist/setup.bat -> double-click
```
Extracts the project, installs pip dependencies, shows usage.

### Option B — From source
```bash
git clone https://github.com/AlexanderGal86/vpn-manager-cli.git
cd vpn-manager-cli
python -m pip install -r requirements.txt
python main.py
```

> Use `python main.py`, not `.\main.py` — the dot-slash form may invoke a
> different Python (Windows file association) that does not have the packages.

---

## Usage

```bash
python main.py              # full pipeline: 1 -> 2 -> 3
python main.py --module 1   # collect proxies only
python main.py --module 2   # speed test only
python main.py --module 3   # connect proxy (needs admin)
```

---

## Project structure

```
vpn-manager-cli/
|
+-- main.py                          <- pipeline entry point + argparse CLI
+-- install.py                       <- self-extracting Python SFX archive
+-- requirements.txt                 <- pip dependencies (ASCII-safe)
|
+-- module1_collector/
|   +-- collector.py                 <- proxy collector
|   +-- AI_HINTS.md
|   +-- output/proxy_list.json       <- generated
|
+-- module2_tester/
|   +-- tester.py                    <- speed tester
|   +-- AI_HINTS.md
|   +-- output/viable_proxies.json   <- generated
|
+-- module3_connector/
|   +-- connector.py                 <- Windows proxy connector
|   +-- AI_HINTS.md
|   +-- output/connection_log.txt    <- generated
|
+-- dist/
    +-- setup.bat                    <- self-extracting BAT installer
```

---

## Module 1 — Proxy Collector

Collects proxies from **10 sources** across three methods:

| Type | Sources |
|---|---|
| HTML scraping | free-proxy-list.net, sslproxies.org, hidemy.name |
| File URLs | ProxyScrape API (HTTP/SOCKS4/SOCKS5), GitHub TheSpeedX |
| JSON API | GeoNode proxylist (paginated) |

**Features:**
- Parallel TCP ping test (40 workers, 3 s timeout)
- TTL cache — addresses checked within the last 6 hours are reused as-is

**Output** (`proxy_list.json`): sorted by `ping_ms` ascending, alive-only.

---

## Module 2 — Speed Tester

| Parameter | Value |
|---|---|
| Batch size | 10 proxies |
| Parallelism | 2 at a time |
| Speed test | Download 2 MB through proxy |
| YouTube threshold | 5 Mbit/s (HD 1080p) |
| Target | 5 viable proxies, then stop |

**Smart re-run:** proxies tested less than 3 hours ago are skipped.
After 3 consecutive failures a proxy is auto-evicted.

---

## Module 3 — Connector (Windows only)

Sets the Windows system proxy via three methods with automatic fallback:

```
Method 1: winreg  ->  HKCU\...\Internet Settings
Method 2: PowerShell Set-ItemProperty (fallback)
Method 3: netsh winhttp import proxy source=ie
```

Commands: `1`..`N` connect, `0` disconnect, `s` status, `q` quit.

> Module 3 requires **Run as Administrator** (registry write).

---

## Configuration

```python
# module1_collector/collector.py
CACHE_TTL_HOURS = 6      # 0 = disable cache
PING_TIMEOUT    = 3
PING_WORKERS    = 40

# module2_tester/tester.py
MIN_SPEED_MBPS   = 5.0   # HD 1080p threshold
RETEST_TTL_HOURS = 3
FAIL_EVICT_COUNT = 3
TARGET_VIABLE    = 5
```

---

## Known limitations

| Issue | Details |
|---|---|
| TCP ping != HTTP reachability | Module 2 does the real HTTP test |
| SOCKS4 vs SOCKS5 | Windows WinINet cannot distinguish them |
| Module 3 Windows only | macOS/Linux not yet implemented |
| HTML sources may break | Update CSS selectors if a site changes layout |

---

## Requirements

- Python 3.10+
- Windows 10/11 for Module 3 (Modules 1–2 also run on Linux/macOS)

```
python -m pip install -r requirements.txt
```

---

## License

MIT — free to use. Comply with your local laws regarding proxy usage.
