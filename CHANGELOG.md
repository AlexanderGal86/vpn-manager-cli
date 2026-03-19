# CHANGELOG — VPN / Proxy Manager

All notable changes documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.1] — 2025-03-18 · Encoding and pip fixes

### Fixed

- **`requirements.txt`**: ASCII-only (no Russian comments). Prevents
  `UnicodeDecodeError` when pip reads the file with a locale encoding (cp1252/cp866).

- **All `.py` modules**: Added at startup on Windows:
  ```python
  sys.stdout.reconfigure(encoding="utf-8", errors="replace")
  sys.stderr.reconfigure(encoding="utf-8", errors="replace")
  ```
  `SetConsoleMode` enables ANSI colours but does **not** change the encoding
  — both calls are needed.

- **`install.py`**: `pip install` now uses `--user` flag.  
  Root cause of the old failure: if setup ran as admin, pip wrote to
  `C:\Program Files\Python3xx` (system scope). The user later ran Python
  without admin and got `ModuleNotFoundError` because user-scoped Python
  has a separate `site-packages`. `--user` avoids this entirely.

- **`install.py`**: Removed `-q` flag from pip so output is visible and
  errors are not silently swallowed.

- **`install.py`**: Added post-install verification:
  ```python
  subprocess.run([sys.executable, "-c", "import requests; print('ok')"])
  ```
  If the import fails after install the user sees a clear message instead
  of a confusing error later.

---

## [1.1.0] — 2025-03-18 · Smart restart (TTL + failure counter)

### Added — Module 1 (collector.py)

- **TTL cache** (`CACHE_TTL_HOURS = 6`):
  - On re-run: loads existing `proxy_list.json`
  - Addresses with `checked_at` younger than TTL → skip (not re-pinged)
  - Addresses older than TTL or without timestamp → re-checked
  - New addresses from sources not in the cache → added
  - `CACHE_TTL_HOURS = 0` disables cache (full rebuild)
- Extracted `_load_cache()` → returns `(fresh_by_key, stale)`
- Extracted `_ping_batch()` — reused for stale and new addresses
- Switched from `datetime.utcnow()` to `datetime.now(timezone.utc)` (timezone-aware)

### Added — Module 2 (tester.py)

- **Retest TTL** (`RETEST_TTL_HOURS = 3`):
  - Fresh viable proxies are skipped without a new speed test
  - If already enough fresh viable ≥ TARGET_VIABLE — testing is skipped
- **Failure counter** (`FAIL_EVICT_COUNT = 3`):
  - Each failed speed test increments `fail_count` in JSON
  - At `fail_count >= FAIL_EVICT_COUNT` the proxy is removed from `viable_proxies.json`
  - A successful test resets the counter to 0
- Result table now shows a **Failures** column (yellow if > 0)
- Extracted: `_load_viable()`, `_is_stale()`, `_evict_failures()`, `_save_and_print()`

### Changed

- `tested_at` is now timezone-aware ISO 8601

---

## [1.0.0] — 2025-03-18 · Initial release

### Added

#### Project structure
- Three independent modules in separate folders
- `main.py` — single pipeline entry point + CLI (`--module 1/2/3`)
- `requirements.txt`, `README.md`
- `install.py` — self-extracting Python SFX

#### Module 1 — Proxy Collector
- HTML table scraping via BeautifulSoup4 + lxml (pagination support)
  - Sources: `free-proxy-list.net`, `sslproxies.org`, `hidemy.name`
- Text file download IP:PORT (`ip:port` line format)
  - Sources: ProxyScrape API (HTTP/SOCKS4/SOCKS5), GitHub TheSpeedX
- JSON API with pagination
  - Sources: GeoNode proxylist API
- Deduplication by `ip:port` key
- Parallel TCP ping test (40 workers, ThreadPoolExecutor)
- Output: `proxy_list.json` sorted by ping

#### Module 2 — Speed Tester
- Batch processing: 10 addresses per batch
- Parallel testing: 2 proxies at a time
- Two-stage test: latency (HEAD) + speed (2 MB download)
- Fallback: 3 test URLs for the download
- YouTube threshold: 5 Mbit/s (`MIN_SPEED_MBPS`)
- Stop on reaching `TARGET_VIABLE` proxies
- Live progress in CLI

#### Module 3 — Proxy Connector
- Interactive CLI menu with numbered proxy list
- Sets Windows system proxy via three methods with fallback:
  1. `winreg` — write to HKCU registry (primary)
  2. PowerShell `Set-ItemProperty` (fallback)
  3. `netsh winhttp import proxy source=ie` (WinHTTP sync)
- Proper SOCKS format: `socks=ip:port`
- `ProxyOverride` to exclude local addresses
- Commands: `0` disconnect, `s` status, `q` quit
- Log all actions to `connection_log.txt`

---

## Roadmap

- [ ] Check specific site accessibility through proxy (YouTube, Google)
- [ ] Automatic proxy rotation on speed drop
- [ ] macOS (`networksetup`) and Linux (`gsettings`) support
- [ ] GUI version (Tkinter or PyQt)
