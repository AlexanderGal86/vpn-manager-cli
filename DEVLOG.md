# DEVLOG — VPN / Proxy Manager Development Journal

Chronological record of decisions, problems encountered, and architectural choices.

---

## 2025-03-18 · Session 1: Planning and architecture

### Initial requirements

User requested a CLI tool composed of three independent modules:
1. Collector — gather IPs from public sources (HTML, files, API) with TCP ping
2. Speed tester — batch test with YouTube threshold (batches of 10, 2 parallel)
3. Windows connector — system proxy via CLI menu

### Key architectural decisions

**Language: Python 3.10+**
- Cross-platform standard library
- `winreg` built-in on Windows CPython
- Good async/threading story via `concurrent.futures`

**Inter-module format: JSON**
Considered CSV and plain TXT — both rejected because they lose metadata
(proxy type, check timestamp). JSON is human-readable and easy to debug.

**Three module folders + `main.py` pipeline**
Modules are independent but linked through `output/` files. This allows
running any single module without the others, useful for debugging.

**ANSI colors via escape codes directly (not colorama)**
Fewer dependencies. Windows 10+ supports ANSI via `SetConsoleMode` —
one `ctypes` call at startup, no third-party library needed.

### Data schemas decided upfront
```
proxy_list.json:     [{ip, port, type, ping_ms, status, checked_at}]
viable_proxies.json: [{...+ speed_mbps, latency_ms, test_status, tested_at, fail_count}]
```

---

## 2025-03-18 · Session 2: Module 1 implementation

### Problem: HTML table structure varies across sites

Each proxy site uses different CSS classes and column order.

**Solution:** Declarative `HTML_SOURCES` config dicts with fields `ip_col`,
`port_col`, `type_col`, `https_values`. The parser is generic; config is
declarative. Adding a new site = adding one dict.

### Problem: ICMP ping requires root on Linux

The `ping3` library needs `sudo` for raw sockets.

**Solution:** TCP ping via `socket.connect()` — no privileges needed,
works everywhere, and measures actual connection establishment time
(more relevant for proxy usability than ICMP round-trip).

### ThreadPoolExecutor vs asyncio

Asyncio would require `aiohttp` and `async`-aware code throughout.
`ThreadPoolExecutor` from stdlib is simpler, sufficient for 40 workers.
For I/O-bound tasks (network requests) GIL is not a bottleneck.

### Source selection rationale

- `free-proxy-list.net`, `sslproxies.org` — stable, simple table structure
- `ProxyScrape API` — reliable, high volume, three protocols
- `TheSpeedX/PROXY-List` on GitHub — frequently updated, simple format
- `GeoNode API` — structured JSON with proper pagination

---

## 2025-03-18 · Session 3: Module 2 implementation

### Problem: display progress for 2 parallel tests

Need to update one CLI line per proxy without flickering or scrambled output.

**Solution:** `threading.Lock` + shared dict `progress = {ip: status_string}`.
Updated in the `as_completed` callback, rendered via `\r` overwrite.
Lock prevents interleaved writes from two threads.

### Speed test URL selection

Requirements: public, no auth, stable, file ≥ 2 MB.
Chose three with geographic diversity for fallback:
- `speedtest.tele2.net` — Sweden, good global coverage
- `ipv4.download.thinkbroadband.com` — UK
- `speedtest.ftp.otenet.gr` — Greece

Fallback pattern: `for url in SPEED_TEST_URLS: try: ... break`

### YouTube speed thresholds

| Quality | Bitrate |
|---|---|
| SD 480p | ~1-2 Mbit/s |
| HD 720p | ~2.5 Mbit/s |
| HD 1080p | ~5 Mbit/s |
| 4K | ~20 Mbit/s |

Chose `MIN_SPEED_MBPS = 5.0` — comfortable HD without buffering.

---

## 2025-03-18 · Session 4: Module 3 (Windows proxy)

### Why three methods for setting proxy?

**winreg** (primary): fastest, direct registry access, no subprocess overhead.
Works on any Windows with Python.

**PowerShell** (fallback): On some corporate machines with Group Policy,
direct `winreg` access may be restricted. PowerShell often runs with a
different privilege context.

**netsh** (supplement): WinINet (browsers) and WinHTTP (system services,
Windows Update) are two separate network stacks. Registry only affects
WinINet. `netsh winhttp import proxy source=ie` syncs WinHTTP from the
IE/WinINet settings.

### SOCKS in Windows system proxy

The `socks=ip:port` format is an undocumented but working WinINet extension.
Chrome, Edge, Firefox all read this field.
SOCKS5 and SOCKS4 are indistinguishable at the Windows system proxy level —
the difference is handled at the application layer.

### ProxyOverride field

Without this field, local addresses also route through the proxy, breaking
local web servers, localhost services, corporate intranets.
Standard exclusion set: `localhost;127.*;10.*;172.16.*;192.168.*;<local>`

---

## 2025-03-18 · Session 5: Distribution

### Why not just a ZIP?

ZIP workflow: download → unzip → find folder → open CMD → `python install.py`.
BAT workflow: double-click → everything happens automatically.

### BAT file: cmd.exe line length limit

`cmd.exe` has an ~8191 character limit per `SET` variable.
Base64 of the archive is ~87 K characters — far exceeds the limit.

**Solution:** Write base64 as 437 `echo CHUNK>> file` lines instead of
one SET variable. `echo` has no length limit. PowerShell then reads the
file and decodes it — called as a single line (no `^` continuation
which is mishandled by cmd.exe in some contexts).

### BAT file encoding: ASCII-only rule

Windows cmd.exe reads `.bat` files with the system codepage (cp866 or cp1252
depending on locale). UTF-8 Cyrillic bytes appear as garbage or cause errors.
**Rule established:** all `.bat` files must be 100% ASCII.
Same rule applies to `requirements.txt` (pip reads it with locale encoding).

### PyInstaller EXE

Bundles everything into one file: Python runtime + stdlib + dependencies.
Size ~7 MB — acceptable for an installer.

Limitation: EXE is OS-specific. Linux produces Linux ELF, Windows produces
Windows PE. Solution: ship `build_exe_source.py` + `build_exe_on_windows.bat`
so users build the EXE on their own Windows machine.

---

## 2025-03-18 · Session 6: Smart re-run (TTL cache)

### Problem: re-run discards the collected database

First run collects 500+ addresses, TCP-pings for 5 minutes.
Re-run an hour later — starts from scratch. Wasteful.

**Solution — TTL cache in Module 1:**
- Addresses with `checked_at` < 6 hours → keep (still fresh)
- Addresses older than TTL → re-ping (may have gone offline)
- New addresses from sources → add and ping

**Solution — re-test in Module 2:**
- Viable proxies may degrade over time
- TTL 3 hours on speed test results
- Failure counter: proxy failing 3 times in a row → evict

### Problem: timezone-naive datetime comparison

Old JSON records lacked timezone in `checked_at`.
`datetime.fromisoformat("2024-01-15T10:30:00")` returns a naive datetime.
Comparing naive with aware (`datetime.now(timezone.utc)`) raises `TypeError`.

Fix:
```python
if checked.tzinfo is None:
    checked = checked.replace(tzinfo=timezone.utc)
```

Also migrated from `datetime.utcnow()` (deprecated in Python 3.12) to
`datetime.now(timezone.utc)`.

---

## 2025-03-19 · Session 7: Encoding fixes

### Problem: garbled output in Windows cmd/PowerShell

All Russian `print()` calls appeared as `???` or boxes in Windows console.

**Root cause:** Python defaults to the Windows console codepage for stdout
(cp866 or cp1252). UTF-8 encoded strings are sent as raw bytes, interpreted
as the wrong encoding.

**Fix:** Added at startup of every `.py` module:
```python
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
```
`errors="replace"` ensures the app never crashes on an unencodable character —
it outputs `?` instead.

Note: `ctypes.windll.kernel32.SetConsoleMode(..., 7)` enables ANSI escape
codes but does NOT change the encoding of stdout. Both calls are needed.

### Problem: pip crashes reading requirements.txt

`UnicodeDecodeError: 'charmap' codec can't decode byte 0x81`

**Root cause:** `requirements.txt` contained Russian comments. pip reads
requirement files using the system locale encoding (cp1252 on Western
Windows). The em-dash `—` in the comments maps to byte `0x97` which cp1252
maps to a valid character, but `0x81` is undefined in cp1252.

**Fix:** Remove all comments from `requirements.txt`. Keep only package names.

### Problem: EXE installer runs in an infinite loop

After extracting files and asking "Install dependencies?", answering Yes
caused the installer to restart from the beginning.

**Root cause:** Inside a PyInstaller frozen EXE, `sys.executable` points to
the EXE itself, not to the Python interpreter. The call:
```python
subprocess.run([sys.executable, "-m", "pip", "install", ...])
```
re-launched `VPN-Manager-Setup.exe` with `-m pip install` as arguments.
The EXE ignored those arguments and started the installer again.

**Fix:** `find_python()` function that detects `sys.frozen` and searches
`PATH` for a real Python binary:
```python
def find_python():
    if not getattr(sys, 'frozen', False):
        return sys.executable   # plain .py run — use current Python
    for cmd in ('python', 'python3', 'py'):
        try:
            r = subprocess.run([cmd, '--version'], capture_output=True, timeout=5)
            if r.returncode == 0:
                return cmd
        except Exception:
            pass
    return None
```

---

## Technical debt and known limitations

| Issue | Status | Priority |
|---|---|---|
| TCP ping != HTTP proxy reachability | Known; Module 2 covers it | Low |
| EXE Windows-only (PyInstaller) | Known; documented | Low |
| SOCKS4/5 indistinguishable in WinINet | Known; Windows limitation | Low |
| No retry on transient network errors in Module 1 | Open | Medium |
| HTML sources break when site layout changes | Known; update `HTML_SOURCES` | High |
| No proxy rotation in Module 3 | On roadmap | Medium |
| Module 3 Windows-only | On roadmap (macOS/Linux) | Medium |
