# VPN / Proxy Manager

> CLI tool for automatic proxy collection, speed testing, and system-level connection on Windows.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2B-informational?logo=windows)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## What it does

Three independent CLI modules connected in a pipeline:

```
[Module 1: Collector] ──proxy_list.json──> [Module 2: Tester] ──viable_proxies.json──> [Module 3: Connector]
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
- Checks for admin rights (auto-relaunches via UAC if needed)
- Detects Python; offers to open python.org if missing
- Extracts the full project, runs pip install, shows usage

### Option B — Standalone EXE (no Python required)
```
1. Download dist/build_exe_source.py + dist/build_exe_on_windows.bat
2. Run build_exe_on_windows.bat  -> produces dist/VPN-Manager-Setup.exe (~7 MB)
3. Run VPN-Manager-Setup.exe
```
The EXE bundles the Python runtime via PyInstaller — nothing needs to be installed.

### Option C — From source
```bash
git clone https://github.com/AlexanderGal86/vpn-manager-cli.git
cd vpn-manager-cli
pip install -r requirements.txt

python main.py              # full pipeline: 1 -> 2 -> 3
python main.py --module 1   # collect only
python main.py --module 2   # speed test only
python main.py --module 3   # connect only
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
|   +-- AI_HINTS.md                  <- architecture notes for AI assistants
|   +-- output/
|       +-- proxy_list.json          <- generated: alive proxies sorted by ping
|
+-- module2_tester/
|   +-- tester.py                    <- speed tester
|   +-- AI_HINTS.md
|   +-- output/
|       +-- viable_proxies.json      <- generated: proxies passing speed threshold
|
+-- module3_connector/
|   +-- connector.py                 <- Windows proxy connector
|   +-- AI_HINTS.md
|   +-- output/
|       +-- connection_log.txt       <- generated: session log
|
+-- dist/
    +-- setup.bat                    <- self-extracting BAT installer (ASCII-only)
    +-- build_exe_source.py          <- EXE installer source (PyInstaller input)
    +-- build_exe_on_windows.bat     <- builds VPN-Manager-Setup.exe on Windows
```

---

## Module 1 — Proxy Collector

Collects proxies from **10 sources** across three methods:

| Type | Sources |
|---|---|
| HTML scraping | free-proxy-list.net, sslproxies.org, hidemy.name (with pagination) |
| File URLs | ProxyScrape API (HTTP / SOCKS4 / SOCKS5), GitHub TheSpeedX lists |
| JSON API | GeoNode proxylist (paginated, up to 3 pages) |

**Features:**
- CSS-selector based pagination — follows "next page" links automatically
- Deduplication by `ip:port` key before pinging
- Parallel TCP ping test (40 workers, 3 s timeout per attempt)
- **TTL cache** — addresses checked within the last 6 hours are reused as-is
- Real-time progress bar in CLI

**Output format** (`proxy_list.json`):
```json
[
  {
    "ip": "1.2.3.4",
    "port": 8080,
    "type": "HTTP",
    "ping_ms": 120.5,
    "status": "alive",
    "checked_at": "2025-03-18T10:30:00+00:00"
  }
]
```
Sorted by `ping_ms` ascending. Only `status == "alive"` entries are saved.

---

## Module 2 — Speed Tester

| Parameter | Value |
|---|---|
| Batch size | 10 proxies |
| Parallelism | 2 at a time |
| Speed test | Download 2 MB through proxy |
| YouTube threshold | 5 Mbit/s (HD 1080p) |
| Target | 5 viable proxies, then stop |

**Smart re-run behaviour:**
- Proxies in `viable_proxies.json` tested less than 3 hours ago are skipped
- A `fail_count` field tracks consecutive failures
- After 3 failures in a row the proxy is auto-evicted from the list
- Successful test resets `fail_count` to 0

**Output format** (`viable_proxies.json`):
```json
[
  {
    "ip": "1.2.3.4", "port": 1080, "type": "SOCKS5",
    "speed_mbps": 8.32, "latency_ms": 95,
    "test_status": "ok",
    "tested_at": "2025-03-18T10:30:00+00:00",
    "fail_count": 0, "ping_ms": 120.5
  }
]
```
Sorted by `speed_mbps` descending.

---

## Module 3 — Connector (Windows only)

Sets the Windows system proxy via three methods with automatic fallback:

```
Method 1: winreg  ->  HKCU\...\Internet Settings  (ProxyEnable / ProxyServer)
Method 2: PowerShell Set-ItemProperty              (fallback if winreg blocked)
Method 3: netsh winhttp import proxy source=ie     (syncs WinHTTP stack)
```

**CLI menu commands:**

| Input | Action |
|---|---|
| `1`..`N` | Connect the selected proxy |
| `0` | Disconnect / reset to no proxy |
| `s` | Show current proxy status from registry |
| `q` | Exit |

**SOCKS support:** Sets `socks=ip:port` in the registry. Works in Chrome, Edge,
Firefox. For full-system interception (UDP, games, Discord) use Proxifier.

> Module 3 requires **Run as Administrator** (registry write).

---

## Configuration

All tuneable constants are at the top of each source file:

```python
# module1_collector/collector.py
CACHE_TTL_HOURS = 6      # 0 = disable cache (always re-collect)
PING_TIMEOUT    = 3      # seconds per TCP attempt
PING_WORKERS    = 40     # parallel workers (safe max: ~80)

# module2_tester/tester.py
MIN_SPEED_MBPS   = 5.0   # YouTube HD threshold
RETEST_TTL_HOURS = 3     # skip proxies tested less than N hours ago
FAIL_EVICT_COUNT = 3     # remove after N consecutive failures (0 = never)
TARGET_VIABLE    = 5     # stop after finding this many viable proxies

# YouTube speed reference:
# SD  480p  ~ 2   Mbit/s
# HD  720p  ~ 2.5 Mbit/s
# HD  1080p ~ 5   Mbit/s  <- default threshold
# 4K        ~ 20  Mbit/s
```

---

## Known limitations

| Issue | Details |
|---|---|
| TCP ping != HTTP reachability | A proxy may accept TCP but fail HTTP — Module 2 catches this |
| SOCKS4 vs SOCKS5 | Windows WinINet cannot distinguish them — apps handle it internally |
| EXE is OS-specific | PyInstaller builds for the current OS; build on Windows for a Windows EXE |
| Module 3 Windows only | macOS (networksetup) and Linux (gsettings) not yet implemented |
| HTML sources may break | Site layout changes can break CSS selectors — update `HTML_SOURCES` config |

---

## Requirements

- Python 3.10+
- Windows 10/11 for Module 3 (Modules 1 and 2 also run on Linux/macOS)

```
pip install -r requirements.txt
# installs: requests, beautifulsoup4, lxml, PySocks
```

---

## AI hints

Each module directory contains `AI_HINTS.md` with documentation for AI assistants:
architecture diagrams, JSON formats, extension points, common pitfalls, integration notes.

---

## License

MIT — free to use. Comply with your local laws regarding proxy usage.
