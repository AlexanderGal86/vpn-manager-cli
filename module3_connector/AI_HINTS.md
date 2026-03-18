# AI_HINTS — Module 3: Proxy Connector

> Этот файл — подсказки для AI-ассистентов, работающих с данным модулем.
> Описывает архитектуру, намерения, точки расширения и частые ловушки.

---

## Назначение модуля

`connector.py` — интерактивный CLI для выбора прокси из списка Module 2
и установки его как системного прокси Windows. Поддерживает три метода
с автоматическим fallback, синхронизирует WinHTTP через netsh.

---

## Архитектура

```
main()
├── load_proxies()          → читает viable_proxies.json
├── show_menu()             → выводит нумерованный список
└── цикл ввода:
    ├── <номер> → set_proxy()
    │   ├── _set_via_winreg()      [метод 1 — основной]
    │   ├── _set_via_powershell()  [метод 2 — fallback]
    │   └── _netsh_import_ie()     [метод 3 — синхронизация WinHTTP]
    ├── 0  → clear_proxy()
    │   ├── _clear_via_winreg()
    │   ├── _clear_via_powershell()
    │   └── _netsh_reset()
    ├── s  → show_status()
    └── q  → выход
```

---

## Три метода установки прокси (Windows)

### Метод 1: winreg (реестр) — основной
```
HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Internet Settings
  ProxyEnable   = 1 (DWORD)
  ProxyServer   = "ip:port"  или  "socks=ip:port" для SOCKS
  ProxyOverride = "localhost;127.*;..." (локальные адреса не через прокси)
```
Работает мгновенно. Требует `import winreg` (встроен в CPython для Windows).

### Метод 2: PowerShell — fallback
```powershell
Set-ItemProperty -Path 'HKCU:\...\Internet Settings' -Name ProxyEnable -Value 1
Set-ItemProperty -Path 'HKCU:\...\Internet Settings' -Name ProxyServer  -Value 'ip:port'
```
Используется если `winreg` недоступен (редко). Чуть медленнее.

### Метод 3: netsh — синхронизация WinHTTP
```
netsh winhttp import proxy source=ie    # применить
netsh winhttp reset proxy               # сбросить
```
WinHTTP — отдельный от WinINet стек (используется системными службами,
Windows Update и т.д.). Без этого шага системные службы не увидят прокси.

---

## Ключевые пути в реестре

```python
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
PS_PATH  = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
```

---

## Формат ProxyServer в реестре

| Тип прокси | Значение ProxyServer |
|---|---|
| HTTP | `1.2.3.4:8080` |
| HTTPS | `1.2.3.4:8080` |
| SOCKS4 | `socks=1.2.3.4:1080` |
| SOCKS5 | `socks=1.2.3.4:1080` |

Windows не различает SOCKS4 и SOCKS5 на уровне системного прокси.

---

## Ограничения Windows системного прокси

```
Работает:
  ✔ HTTP/HTTPS трафик браузеров (Chrome, Edge, Firefox)
  ✔ Большинство приложений использующих WinINet/WinHTTP
  ✔ Windows Update, Microsoft Store

Не работает (нужен Proxifier или аналог):
  ✖ UDP трафик (игры, VoIP)
  ✖ Приложения с собственным стеком сетей (Telegram Desktop, Discord)
  ✖ Raw socket соединения
```

---

## Логирование

Все действия записываются в `output/connection_log.txt`:
```
[2024-01-15 10:30:00] === SESSION START ===
[2024-01-15 10:30:05] SET winreg HTTP 1.2.3.4:8080
[2024-01-15 10:31:00] CLEAR winreg
[2024-01-15 10:31:00] NETSH winhttp reset
[2024-01-15 10:31:00] SESSION END (quit)
```

---

## Частые ловушки

1. **Нужны права администратора** для записи в реестр и выполнения `netsh`.
   Без них `winreg.OpenKey(..., KEY_SET_VALUE)` выбросит `PermissionError`.
   Скрипт предупреждает, но не принудительно перезапускает.

2. **WINREG_OK = False на Linux/macOS** — `import winreg` доступен только
   на Windows. На других платформах обе функции winreg вернут `False` и
   выполнение упадёт к предупреждению "только для Windows".

3. **ProxyOverride** — без этого поля локальные адреса (127.0.0.1, localhost)
   тоже пойдут через прокси и сломают локальные сервисы.

4. **netsh требует прав администратора** — если UAC заблокирует,
   `subprocess.run(["netsh", ...])` не вызовет исключение, просто не сделает ничего.
   Лучше запускать весь скрипт от администратора.

5. **SOCKS через системный прокси в старых приложениях** — IE и некоторые
   legacy-приложения не поддерживают SOCKS через системные настройки.

---

## Расширение: добавить macOS/Linux поддержку

### macOS (networksetup)
```python
def _set_macos(ip, port, ptype):
    service = "Wi-Fi"  # или "Ethernet"
    if ptype in ("SOCKS5", "SOCKS4"):
        subprocess.run(["networksetup", "-setsocksfirewallproxy", service, ip, str(port)])
    else:
        subprocess.run(["networksetup", "-setwebproxy", service, ip, str(port)])
        subprocess.run(["networksetup", "-setsecurewebproxy", service, ip, str(port)])
```

### Linux (gsettings / environment)
```python
def _set_linux(ip, port):
    subprocess.run(["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"])
    subprocess.run(["gsettings", "set", "org.gnome.system.proxy.http", "host", ip])
    subprocess.run(["gsettings", "set", "org.gnome.system.proxy.http", "port", str(port)])
```

---

## Зависимости

Только стандартная библиотека:
- `winreg` — встроен в CPython/Windows
- `subprocess` — для PowerShell и netsh
- `os`, `sys`, `json`

---

## Интеграция

- **Вход**: `../module2_tester/output/viable_proxies.json`
- **Выход**: `output/connection_log.txt` (только лог)
- Системное состояние: реестр Windows (HKCU)
