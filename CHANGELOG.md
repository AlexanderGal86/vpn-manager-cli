# CHANGELOG — VPN / Proxy Manager

All notable changes are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.1] — 2025-03-19 · Encoding fixes + missing files

### Fixed
- **`dist/setup.bat`**: Complete rewrite — ASCII-only, PowerShell called as single
  line (no `^` multi-line continuation). Eliminates garbled output in `cmd.exe`.
- **`requirements.txt`**: Removed Russian comments. `pip` on Windows reads files
  with `cp1252` by default; non-ASCII bytes caused `UnicodeDecodeError`.
- **`dist/build_exe_on_windows.bat`**: Translated to English — ASCII-only.
- **All `.py` modules**: Added `sys.stdout.reconfigure(encoding="utf-8")` block
  after `SetConsoleMode`. Without this, all `print()` output is garbled in
  `cmd.exe` / PowerShell on Russian Windows.
- **`dist/build_exe_source.py`**: Fixed infinite loop when running as PyInstaller
  EXE. `sys.executable` inside a frozen EXE points to the EXE itself, not Python.
  Calling `[sys.executable, "-m", "pip", ...]` re-launched the installer instead of
  pip, creating an endless loop. Fixed by `find_python()` which searches `PATH`
  for a real Python binary when `sys.frozen` is detected.
- **`.gitignore`**: Removed Russian comments — ASCII-only.

### Added
- **`install.py`**: Self-extracting Python SFX added to repo root (was missing
  from initial commit).
- **`dist/build_exe_on_windows.bat`**: Added to repo (was missing from initial
  commit).
- All `.md` files expanded with full English documentation.

---

## [1.2.0] — 2025-03-18 · Windows distributables

### Added
- **`dist/setup.bat`** — self-extracting BAT file (~95 KB)
  - Admin rights check with auto-relaunch via UAC
  - Python detection; offers `winget install` or python.org if missing
  - Project archive embedded as base64; decoded by PowerShell into `%TEMP%`
  - Temp file cleaned up after install
- **`dist/build_exe_source.py`** — source for building standalone EXE via PyInstaller
  - Embedded project archive
  - Install folder selection (default `~/vpn-manager`)
  - Creates `VPN Manager.bat` shortcut on Desktop
  - Auto-relaunch as admin via `ShellExecuteW`
- **`dist/build_exe_on_windows.bat`** — one-click EXE builder

### Notes
- EXE must be built on Windows (PyInstaller produces OS-native binaries)
- Standalone EXE size ~7 MB (includes Python runtime)

---

## [1.1.0] — 2025-03-18 · Smart re-run (TTL + failure counter)

### Added — Module 1 (`collector.py`)
- **TTL cache** (`CACHE_TTL_HOURS = 6`):
  - On re-run, loads existing `proxy_list.json`
  - Addresses with `checked_at` younger than TTL are kept as-is (not re-pinged)
  - Addresses older than TTL or without timestamp are re-checked
  - New addresses from sources not in cache are always pinged
  - `CACHE_TTL_HOURS = 0` disables cache (full overwrite)
- Extracted `_load_cache()` → returns `(fresh_by_key, stale)`
- Extracted `_ping_batch()` — reused for both stale and new addresses
- Switched from `datetime.utcnow()` (deprecated in Python 3.12) to
  `datetime.now(timezone.utc)` — all timestamps are now timezone-aware

### Added — Module 2 (`tester.py`)
- **Re-test TTL** (`RETEST_TTL_HOURS = 3`):
  - Fresh viable proxies are skipped without re-testing
  - If enough fresh viable proxies exist (≥ TARGET_VIABLE), testing is skipped
- **Failure counter** (`FAIL_EVICT_COUNT = 3`):
  - Each speed test failure increments `fail_count` in the JSON
  - When `fail_count >= FAIL_EVICT_COUNT` the proxy is removed from `viable_proxies.json`
  - Successful test resets counter to 0
- Result table gained a **Failures** column (shown in yellow when > 0)
- Extracted helpers: `_load_viable()`, `_is_stale()`, `_evict_failures()`,
  `_save_and_print()`

### Changed
- `tested_at` is now a timezone-aware ISO 8601 string

---

## [1.0.0] — 2025-03-18 · Initial release

### Added

#### Project structure
- Three independent modules in separate folders
- `main.py` — unified pipeline + CLI (`--module 1/2/3`)
- `requirements.txt`
- `README.md`
- `install.py` — self-extracting Python script

#### Module 1 — Proxy Collector (`module1_collector/collector.py`)
- HTML table scraping via BeautifulSoup4 + lxml
  - Pagination support via CSS "next page" selector
  - Sources: `free-proxy-list.net`, `sslproxies.org`, `hidemy.name`
- Text file download (IP:PORT format, one per line)
  - Sources: ProxyScrape API (HTTP/SOCKS4/SOCKS5), GitHub TheSpeedX
- JSON API with pagination
  - Source: GeoNode proxylist API
- Deduplication by `ip:port` key
- Parallel TCP ping test (40 workers, ThreadPoolExecutor)
  - Real-time progress bar via `\r` overwrite
  - 3-second timeout per attempt
- Output: `proxy_list.json` sorted by ping, alive-only

#### Module 2 — Speed Tester (`module2_tester/tester.py`)
- Batch processing: 10 addresses per batch
- Parallel testing: 2 proxies simultaneously
- Two-stage test: latency (HEAD request) + speed (2 MB download)
- Fallback: 3 test URLs for download
- YouTube threshold: 5 Mbit/s (configurable via `MIN_SPEED_MBPS`)
- Stops after reaching `TARGET_VIABLE` suitable proxies
- Live CLI progress update (line overwrite)
- Result table: IP, type, speed, latency

#### Module 3 — Proxy Connector (`module3_connector/connector.py`)
- Interactive CLI menu with numbered proxy list
- Sets Windows system proxy via three methods with fallback:
  1. `winreg` — write to registry HKCU (primary method)
  2. PowerShell `Set-ItemProperty` (fallback)
  3. `netsh winhttp import proxy source=ie` (WinHTTP sync)
- Correct SOCKS format: `socks=ip:port`
- `ProxyOverride` to exclude local addresses
- Disconnect proxy: command `0`
- Show current proxy status: command `s`
- All actions logged to `connection_log.txt`
- Warning about SOCKS limitations on Windows

---

## Roadmap

- [ ] Per-site reachability check (YouTube, Google) through the proxy
- [ ] Automatic proxy rotation on speed degradation
- [ ] macOS support (`networksetup`) and Linux (`gsettings`)
- [ ] GUI version (Tkinter or PyQt)
- [ ] Windows Toast notification when a fast proxy is found
- [ ] Export to PAC file and Proxychains config format
