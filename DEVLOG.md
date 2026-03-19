# DEVLOG — Development Journal VPN / Proxy Manager

Chronological record of decisions, problems, and architectural choices.

---

## 2025-03-18 · Session 1: Planning and architecture

### Initial requirements

User requested a CLI tool with three independent modules:
1. Collector: scrape IPs from open sources (HTML, files, API) + TCP ping
2. Speed tester: batches of 10, 2 parallel, YouTube threshold
3. Connector: Windows system proxy with CLI menu

**Key architectural decisions:**

- Language: Python 3.10+ — cross-platform, good stdlib, `winreg` built-in for Windows
- Inter-module format: JSON (structured, human-readable, easy to debug).
  CSV and TXT rejected — lose metadata (type, timestamp)
- Three module folders + `main.py` for pipeline — modules are independent,
  connected via files in `output/`
- ANSI colors via escape codes directly (no colorama) — fewer dependencies,
  Windows 10+ supports them via `SetConsoleMode`

### Output data structure

```
proxy_list.json:     [{ip, port, type, ping_ms, status, checked_at}]
viable_proxies.json: [{...+ speed_mbps, latency_ms, test_status, tested_at, fail_count}]
```

---

## 2025-03-18 · Session 2: Module 1 implementation

### Problem: varied HTML table structures

Different sites use different CSS classes and column order.  
**Solution**: config dicts `HTML_SOURCES` with `ip_col`, `port_col`, `type_col`,
`https_values`. The parser is generic; config is declarative.

### Problem: ICMP ping requires root on Linux

`ping3` needs `sudo` for raw sockets.  
**Solution**: TCP ping via `socket.connect()` — no privileges needed,
works everywhere, measures real connection setup time.

### Architectural choice: ThreadPoolExecutor vs asyncio

asyncio would require `aiohttp` and async-aware code throughout.
ThreadPoolExecutor from stdlib, simpler, sufficient for 40 workers.
GIL is not a problem for I/O-bound tasks (network requests).

---

## 2025-03-18 · Session 3: Module 2 implementation

### Problem: showing progress for 2 parallel tests

Need to update one CLI line for each of the two parallel proxies.  
**Solution**: `threading.Lock` + shared dict `progress = {ip: status_string}`,
updated in each future callback, printed via `\r` overwrite.

### Speed test URL selection

Requirements: open, no auth, stable, file ≥ 2 MB.
- `speedtest.tele2.net` — Swedish CDN, good global coverage
- `ipv4.download.thinkbroadband.com` — UK, alternative
- `speedtest.ftp.otenet.gr` — Greek, third fallback

**Fallback strategy**: `for url in SPEED_TEST_URLS: try: ... break`

### YouTube threshold

- SD 480p:  ~1–2 Mbit/s
- HD 720p:  ~2.5 Mbit/s
- HD 1080p: ~5 Mbit/s  ← chosen
- 4K:       ~20 Mbit/s

---

## 2025-03-18 · Session 4: Module 3 (Windows Proxy)

### Why three proxy-setting methods?

**winreg** (primary): fastest, direct registry access, no external processes.
Works on any Windows with Python.

**PowerShell** (fallback): on some corporate machines with group policies,
direct `winreg` may be restricted. PowerShell often has different access.

**netsh** (supplement): WinINet (browsers) and WinHTTP (system services) are
two separate stacks. Registry changes only WinINet. `netsh winhttp import proxy
source=ie` syncs WinHTTP with IE/WinINet settings.

### SOCKS in Windows system proxy

Format `socks=ip:port` — undocumented but working WinINet extension.
Chrome, Edge, Firefox all read this field. SOCKS5 and SOCKS4 are
indistinguishable at the WinINet level — the difference is handled by the app.

---

## 2025-03-18 · Session 5: Distribution

### setup.bat: why not just a ZIP?

ZIP requires: unzip → find folder → open CMD → `python install.py`.  
BAT: double-click → everything automatic.

**Problem**: `cmd.exe` has a ~8191 char limit on SET variable lines.
Base64 of the archive is ~87K chars.  
**Solution**: PowerShell heredoc with `$b64 += "chunk"` — no such limit.
Single-line PowerShell call: `[Convert]::FromBase64String($b)`.

**Problem**: BAT file encoding. Windows cmd defaults to CP866/CP1251.  
**Solution**: write BAT as ASCII-only, avoid Cyrillic in BAT commands.

---

## 2025-03-18 · Session 6: Smart restart

### Problem: re-run discards already-collected proxy base

First run collects 500+ addresses, ping-checks them in 5 minutes.
Re-run an hour later — starts from scratch. Wasteful.

**Solution — TTL cache in Module 1**:
- Addresses with `checked_at` < 6 hours → keep (still fresh)
- Addresses older → re-check (may have died)
- New addresses from sources → add and check

**Solution — retest in Module 2**:
- Viable proxies degrade over time
- 3-hour TTL on speed test results
- Failure counter: proxy that fails 3 times in a row → evict

### Problem: timezone-naive datetime comparison

Old records in JSON had no timezone in `checked_at`.
`datetime.fromisoformat("2024-01-15T10:30:00")` returns naive datetime.
Comparing naive with aware (`datetime.now(timezone.utc)`) → `TypeError`.

**Fix**:
```python
if checked.tzinfo is None:
    checked = checked.replace(tzinfo=timezone.utc)
```

Also switched from deprecated `datetime.utcnow()` to `datetime.now(timezone.utc)`.

---

## 2025-03-18 · Session 7: Encoding and pip scope bugs

### Bug: pip UnicodeDecodeError (cp1252)

**Root cause**: `requirements.txt` had Russian inline comments. pip reads it
with the system locale encoding (cp1252/cp866 on Russian Windows).  
**Fix**: ASCII-only `requirements.txt` — package names only, no comments.

### Bug: garbled console output on Windows

**Root cause**: Python stdout defaults to cp866/cp1252 on Windows cmd.
`SetConsoleMode` enables ANSI colors but does **not** change the encoding.  
**Fix**: added to all `.py` modules at startup:
```python
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```
Both calls are necessary and independent.

### Bug: ModuleNotFoundError after installation

**Root cause**: setup.bat ran as admin → pip installed to
`C:\Program Files\Python313\` (system scope). User ran `main.py` without admin
→ Python resolved user-scoped `site-packages` (in `%APPDATA%`) which was empty.

**Fix**: `pip install --user` — installs to user's own `site-packages`
regardless of admin state. Each Windows user gets their own package set.
No admin needed for install.

**Secondary fix**: use `python main.py` not `.\main.py` — the dot-slash form
may invoke Python via Windows file association which can be a different
installation.

---

## Technical debt and known limitations

| Issue | Status | Priority |
|---|---|---|
| TCP ping != HTTP proxy reachability | Known; Module 2 handles it | Low |
| SOCKS4 vs SOCKS5 indistinguishable in WinINet | Known; Windows limitation | Low |
| No retry on transient network errors in Module 1 | Open | Medium |
| No proxy rotation in Module 3 | On roadmap | Medium |
| HTML sources can break on layout change | Known | High |
