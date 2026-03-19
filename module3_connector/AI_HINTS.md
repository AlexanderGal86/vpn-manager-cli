# AI_HINTS — Module 3: Proxy Connector

Hints for AI assistants working with this module.
Covers architecture, intent, extension points, and common pitfalls.

---

## Purpose

`connector.py` is an interactive CLI for selecting a proxy from Module 2's
output and setting it as the Windows system proxy. Supports three fallback
methods and syncs the WinHTTP stack via `netsh`.

---

## Architecture

```
main()
├── load_proxies()          -> reads viable_proxies.json; exits if missing
├── show_menu()             -> numbered table with speed + latency columns
└── input loop:
    ├── <number> -> set_proxy(ip, port, type)
    │   ├── _set_via_winreg()      [method 1 — primary]
    │   ├── _set_via_powershell()  [method 2 — fallback]
    │   └── _netsh_import_ie()     [method 3 — WinHTTP sync]
    ├── 0  -> clear_proxy()
    │   ├── _clear_via_winreg()
    │   ├── _clear_via_powershell()
    │   └── _netsh_reset()
    ├── s  -> show_status()        reads ProxyEnable + ProxyServer from registry
    └── q  -> exit
```

---

## Three proxy-setting methods

### Method 1: winreg (registry) — primary
```
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings
  ProxyEnable   = 1 (DWORD)
  ProxyServer   = "ip:port"          for HTTP / HTTPS
                  "socks=ip:port"    for SOCKS4 / SOCKS5
  ProxyOverride = "localhost;127.*;10.*;172.16.*;192.168.*;<local>"
```
Instant, no subprocess. Requires `import winreg` (CPython Windows only).

### Method 2: PowerShell — fallback
```powershell
Set-ItemProperty -Path 'HKCU:\...\Internet Settings' -Name ProxyEnable -Value 1
Set-ItemProperty -Path 'HKCU:\...\Internet Settings' -Name ProxyServer  -Value 'ip:port'
```
Used when `winreg` access is blocked by Group Policy (rare).
Detected by checking the return value of `_set_via_winreg()`.

### Method 3: netsh — WinHTTP sync
```
netsh winhttp import proxy source=ie    # copy IE/WinINet settings to WinHTTP
netsh winhttp reset proxy               # reset WinHTTP
```
WinINet (browsers) and WinHTTP (system services, Windows Update, WCF apps)
are two separate network stacks. The registry only affects WinINet.
Without `netsh`, system services do not see the new proxy.

---

## Registry paths used

```python
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
PS_PATH  = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
```

---

## ProxyServer registry value format

| Proxy type | ProxyServer value |
|---|---|
| HTTP | `1.2.3.4:8080` |
| HTTPS | `1.2.3.4:8080` |
| SOCKS4 | `socks=1.2.3.4:1080` |
| SOCKS5 | `socks=1.2.3.4:1080` |

Windows WinINet cannot distinguish SOCKS4 from SOCKS5 at the system level.
The application itself negotiates the SOCKS version during handshake.

---

## What the system proxy affects

```
Works:
  + HTTP/HTTPS traffic from browsers (Chrome, Edge, Firefox)
  + Most apps using WinINet/WinHTTP (after netsh sync)
  + Windows Update, Microsoft Store

Does NOT work without Proxifier or similar:
  - UDP traffic (games, VoIP, WebRTC)
  - Apps with their own network stack (Telegram Desktop, Discord)
  - Raw socket connections
```

---

## Session log format

All actions are appended to `output/connection_log.txt`:
```
[2025-03-18 10:30:00] === SESSION START ===
[2025-03-18 10:30:05] SET winreg HTTP 1.2.3.4:8080
[2025-03-18 10:31:00] NETSH winhttp import ie
[2025-03-18 10:32:00] CLEAR winreg
[2025-03-18 10:32:00] NETSH winhttp reset
[2025-03-18 10:32:00] SESSION END (quit)
```

---

## Common pitfalls

**1. Administrator rights required**
`winreg.OpenKey(..., KEY_SET_VALUE)` raises `PermissionError` without admin.
`netsh` silently does nothing without admin (no exception raised).
The script warns the user but does not force a relaunch.
For reliable operation, always run as Administrator.

**2. `WINREG_OK = False` on Linux / macOS**
`import winreg` is only available in CPython on Windows. On other platforms
both `winreg` functions return `False` and execution falls to the
"Windows only" warning. This is intentional — the module is Windows-only.

**3. Windows encoding: `reconfigure` is required**
All `print()` output uses UTF-8. Windows cmd.exe and PowerShell default to
cp866/cp1252. Without `sys.stdout.reconfigure(encoding="utf-8")`, all menu
text and status messages appear as garbage.
Already present in the file — do not remove.

**4. `ProxyOverride` prevents broken local services**
Without this field, `localhost` and `127.0.0.1` also route through the proxy,
breaking local web servers, development environments, and corporate intranets.
Always set it when enabling the proxy.

**5. `netsh` requires admin — silent failure**
If UAC blocks `netsh`, `subprocess.run(["netsh", ...])` returns without error
but the WinHTTP stack is not updated. System services keep using the old proxy.
This is why running the entire script as Administrator is recommended.

**6. SOCKS in legacy apps**
Internet Explorer and some legacy Windows applications do not honour
`socks=ip:port` in the system proxy settings. Only modern apps do.

---

## Extension: add macOS support

```python
def _set_macos(ip, port, ptype):
    service = "Wi-Fi"   # or "Ethernet"
    if ptype in ("SOCKS5", "SOCKS4"):
        subprocess.run(["networksetup", "-setsocksfirewallproxy",
                         service, ip, str(port)])
    else:
        subprocess.run(["networksetup", "-setwebproxy",
                         service, ip, str(port)])
        subprocess.run(["networksetup", "-setsecurewebproxy",
                         service, ip, str(port)])
```

## Extension: add Linux support (GNOME)

```python
def _set_linux(ip, port):
    subprocess.run(["gsettings", "set", "org.gnome.system.proxy",
                     "mode", "manual"])
    subprocess.run(["gsettings", "set", "org.gnome.system.proxy.http",
                     "host", ip])
    subprocess.run(["gsettings", "set", "org.gnome.system.proxy.http",
                     "port", str(port)])
```

---

## Dependencies

Standard library only:
- `winreg` — built into CPython on Windows
- `subprocess` — for PowerShell and netsh calls
- `os`, `sys`, `json`, `datetime`

---

## Integration

- **Input**: `../module2_tester/output/viable_proxies.json`
- **Output**: `output/connection_log.txt` (append-only action log)
- **System state modified**: Windows registry `HKCU` + WinHTTP via netsh
