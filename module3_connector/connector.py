"""
MODULE 3 — PROXY CONNECTOR
CLI-интерфейс для выбора прокси из списка Модуля 2
и установки системного прокси Windows.
Методы: реестр (winreg) → PowerShell fallback → netsh.
Выход: module3_connector/output/connection_log.txt
"""

import os
import sys
import json
import subprocess
import time
from datetime import datetime

# ─── Пути ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE  = os.path.join(BASE_DIR, "..", "module2_tester", "output", "viable_proxies.json")
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")
LOG_FILE    = os.path.join(OUTPUT_DIR, "connection_log.txt")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── ANSI-цвета ──────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
        import winreg   # только Windows
        WINREG_OK = True
    except Exception:
        WINREG_OK = False
else:
    WINREG_OK = False

G   = "\033[92m";  Y = "\033[93m";  R = "\033[91m"
C   = "\033[96m";  B = "\033[1m";   RS = "\033[0m";  DIM = "\033[2m"

# Путь в реестре для настроек Internet Explorer / WinINet
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

# ─── Вспомогательные функции ─────────────────────────────────────────────────
def banner():
    print(f"""
{C}{B}╔══════════════════════════════════════════════╗
║   MODULE 3 — PROXY CONNECTOR                 ║
║   Выбор и подключение системного прокси      ║
╚══════════════════════════════════════════════╝{RS}
""")

def log(msg: str):
    """Пишет в лог-файл и выводит в CLI."""
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(f"  {DIM}{line}{RS}")

def ok(msg):   print(f"  {G}✔{RS}  {msg}")
def warn(msg): print(f"  {Y}⚠{RS}  {msg}")
def err(msg):  print(f"  {R}✖{RS}  {msg}")


# ─── Загрузка списка ─────────────────────────────────────────────────────────
def load_proxies() -> list:
    if not os.path.exists(INPUT_FILE):
        err(f"Файл не найден: {INPUT_FILE}")
        print(f"  {Y}Сначала запустите Модуль 2 (tester.py){RS}\n")
        sys.exit(1)
    with open(INPUT_FILE, encoding="utf-8") as f:
        proxies = json.load(f)
    if not proxies:
        err("Список viable_proxies.json пуст. Запустите Модуль 2.")
        sys.exit(1)
    return proxies


# ─── Меню выбора ─────────────────────────────────────────────────────────────
def show_menu(proxies: list):
    print(f"\n  {B}Доступные прокси:{RS}\n")
    print(f"  {'№':>3}  {'IP-адрес':15}  {'Порт':>5}  "
          f"{'Тип':<6}  {'Скорость':>12}  {'Задержка':>9}")
    print(f"  {'─'*60}")
    for i, p in enumerate(proxies):
        spd = f"{p['speed_mbps']:.2f} Мбит/с"
        lat = f"{p.get('latency_ms', '?')} ms"
        print(
            f"  {C}{i + 1:>3}.{RS}  "
            f"{p['ip']:15}  {p['port']:>5}  "
            f"[{p['type']:<6}]  "
            f"{G}{spd:>12}{RS}  "
            f"{lat:>9}"
        )
    print(f"\n  {DIM}  0.  Отключить прокси (сбросить системные настройки){RS}")
    print(f"  {DIM}  s.  Показать текущий статус прокси{RS}")
    print(f"  {DIM}  q.  Выход{RS}\n")


# ─── Метод 1: Реестр Windows (winreg) ────────────────────────────────────────
def _set_via_winreg(ip: str, port: int, ptype: str) -> bool:
    if not WINREG_OK:
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        # SOCKS: "socks=ip:port"  /  HTTP(S): "ip:port"
        if ptype.upper() in ("SOCKS5", "SOCKS4"):
            server = f"socks={ip}:{port}"
        else:
            server = f"{ip}:{port}"

        winreg.SetValueEx(key, "ProxyEnable",   0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer",   0, winreg.REG_SZ,    server)
        winreg.SetValueEx(
            key, "ProxyOverride", 0, winreg.REG_SZ,
            "localhost;127.*;10.*;172.16.*;192.168.*;<local>"
        )
        winreg.CloseKey(key)
        return True
    except Exception as e:
        warn(f"winreg: {e}")
        return False


def _clear_via_winreg() -> bool:
    if not WINREG_OK:
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        warn(f"winreg clear: {e}")
        return False


# ─── Метод 2: PowerShell fallback ────────────────────────────────────────────
_PS_BASE = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"

def _run_ps(script: str) -> bool:
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=12
        )
        return "PS_OK" in result.stdout
    except Exception as e:
        warn(f"PowerShell: {e}")
        return False


def _set_via_powershell(ip: str, port: int, ptype: str) -> bool:
    if sys.platform != "win32":
        return False
    server = f"socks={ip}:{port}" if ptype.upper() in ("SOCKS5", "SOCKS4") else f"{ip}:{port}"
    script = f"""
$p = '{_PS_BASE}'
Set-ItemProperty -Path $p -Name ProxyEnable   -Value 1
Set-ItemProperty -Path $p -Name ProxyServer   -Value '{server}'
Set-ItemProperty -Path $p -Name ProxyOverride -Value 'localhost;127.*;10.*;172.16.*;192.168.*;<local>'
Write-Output 'PS_OK'
"""
    return _run_ps(script)


def _clear_via_powershell() -> bool:
    if sys.platform != "win32":
        return False
    script = f"""
$p = '{_PS_BASE}'
Set-ItemProperty -Path $p -Name ProxyEnable -Value 0
Write-Output 'PS_OK'
"""
    return _run_ps(script)


# ─── Метод 3: netsh (WinHTTP — дополнительно) ────────────────────────────────
def _netsh_import_ie():
    """Синхронизирует WinHTTP с настройками IE/WinINet."""
    try:
        subprocess.run(
            ["netsh", "winhttp", "import", "proxy", "source=ie"],
            capture_output=True, timeout=8
        )
        ok("WinHTTP обновлён (netsh import ie)")
        log("NETSH winhttp import ie")
    except Exception:
        pass


def _netsh_reset():
    """Сбрасывает WinHTTP-прокси."""
    try:
        subprocess.run(
            ["netsh", "winhttp", "reset", "proxy"],
            capture_output=True, timeout=8
        )
        ok("WinHTTP сброшен (netsh reset)")
        log("NETSH winhttp reset")
    except Exception:
        pass


# ─── Статус текущего прокси ──────────────────────────────────────────────────
def show_status():
    if sys.platform != "win32":
        warn("Статус прокси доступен только на Windows.")
        return
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ
        )
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        server = ""
        try:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
        except Exception:
            pass
        winreg.CloseKey(key)
        status_tag = f"{G}ВКЛЮЧЁН{RS}" if enabled else f"{Y}ВЫКЛЮЧЕН{RS}"
        print(f"\n  Системный прокси: {status_tag}")
        if enabled and server:
            print(f"  Адрес:            {C}{server}{RS}")
    except Exception as e:
        err(f"Не удалось прочитать реестр: {e}")


# ─── Унифицированный set_proxy ────────────────────────────────────────────────
def set_proxy(ip: str, port: int, ptype: str):
    print(f"\n  {B}Устанавливаем прокси:{RS}  {C}{ip}:{port}{RS}  [{ptype}]")

    if sys.platform != "win32":
        warn("Установка системного прокси доступна только на Windows.")
        log(f"SKIP set_proxy (not Windows): {ptype} {ip}:{port}")
        return

    # Попытка 1: реестр
    if _set_via_winreg(ip, port, ptype):
        ok("Прокси установлен через реестр Windows (winreg)")
        log(f"SET winreg {ptype} {ip}:{port}")
    else:
        # Попытка 2: PowerShell
        warn("Реестр недоступен — пробуем PowerShell…")
        if _set_via_powershell(ip, port, ptype):
            ok("Прокси установлен через PowerShell")
            log(f"SET powershell {ptype} {ip}:{port}")
        else:
            err("Не удалось установить прокси ни одним из методов.")
            log(f"SET FAILED {ip}:{port}")
            return

    # Синхронизация WinHTTP
    _netsh_import_ie()

    # Предупреждение для SOCKS
    if ptype.upper() in ("SOCKS5", "SOCKS4"):
        print()
        warn(f"SOCKS-прокси установлен в системные настройки.")
        print(f"     {DIM}Браузеры (Chrome, Edge, Firefox) и большинство приложений")
        print(f"     поддерживают этот режим. Для полного перехвата всего")
        print(f"     трафика (включая UDP/игры) используйте Proxifier.{RS}")


# ─── Унифицированный clear_proxy ─────────────────────────────────────────────
def clear_proxy():
    print(f"\n  {B}Отключаем системный прокси…{RS}")

    if sys.platform != "win32":
        warn("Только для Windows.")
        return

    if _clear_via_winreg():
        ok("Прокси отключён (winreg)")
        log("CLEAR winreg")
    elif _clear_via_powershell():
        ok("Прокси отключён (PowerShell)")
        log("CLEAR powershell")
    else:
        err("Не удалось отключить прокси.")
        log("CLEAR FAILED")
        return

    _netsh_reset()
    print(f"  {G}Прокси полностью отключён.{RS}")


# ─── Главный цикл ────────────────────────────────────────────────────────────
def main():
    banner()
    proxies = load_proxies()
    print(f"  Загружено вариантов: {C}{B}{len(proxies)}{RS}")
    print(f"  Лог:                 {DIM}{LOG_FILE}{RS}")

    log("=== SESSION START ===")

    while True:
        show_menu(proxies)
        try:
            choice = input(f"  {C}Выбор>{RS} ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n  {Y}Прерывание. Выход.{RS}")
            log("SESSION END (interrupt)")
            break

        print()

        if choice == "q":
            print(f"  {Y}Выход.{RS}")
            log("SESSION END (quit)")
            break

        elif choice == "0":
            clear_proxy()

        elif choice == "s":
            show_status()

        elif choice.isdigit() and 1 <= int(choice) <= len(proxies):
            p = proxies[int(choice) - 1]
            set_proxy(p["ip"], p["port"], p["type"])

        else:
            warn(f"Неверный ввод: '{choice}'. "
                 f"Введите номер от 1 до {len(proxies)}, 0, s или q.")

        print()
        input(f"  {DIM}[Enter] для продолжения…{RS}")


if __name__ == "__main__":
    main()
