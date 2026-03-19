"""
MODULE 1 — PROXY COLLECTOR
Собирает IP-адреса прокси из HTML-страниц, файловых URL и API.
Проверяет доступность через TCP-пинг.
Выход: module1_collector/output/proxy_list.json
"""

import os
import sys
import json
import socket
import time
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from bs4 import BeautifulSoup

# ─── Пути ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "proxy_list.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── ANSI-цвета (Windows 10+ поддерживает) ───────────────────────────────────
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

G   = "\033[92m"   # зелёный
Y   = "\033[93m"   # жёлтый
R   = "\033[91m"   # красный
C   = "\033[96m"   # голубой
B   = "\033[1m"    # жирный
RS  = "\033[0m"    # сброс
DIM = "\033[2m"    # тёмный

# ─── Хелперы вывода ───────────────────────────────────────────────────────────
def banner():
    print(f"""
{C}{B}╔══════════════════════════════════════════════╗
║   MODULE 1 — PROXY COLLECTOR                 ║
║   Сбор, фильтрация и пинг-проверка прокси    ║
╚══════════════════════════════════════════════╝{RS}
""")

def step_msg(step, total, msg):
    print(f"  {C}[{step}/{total}]{RS} {msg}")

def ok(msg):   print(f"  {G}✔{RS}  {msg}")
def warn(msg): print(f"  {Y}⚠{RS}  {msg}")
def err(msg):  print(f"  {R}✖{RS}  {msg}")
def info(msg): print(f"     {DIM}{msg}{RS}")

# ─── Конфигурация источников ──────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# HTML-источники — таблицы на веб-страницах
HTML_SOURCES = [
    {
        "name":           "free-proxy-list.net",
        "start_url":      "https://free-proxy-list.net/",
        "row_sel":        "table tbody tr",
        "ip_col":         0,
        "port_col":       1,
        "type_col":       6,           # "yes" → HTTPS
        "https_values":   ["yes"],
        "next_page_sel":  None,        # нет пагинации
        "max_pages":      1,
    },
    {
        "name":           "sslproxies.org",
        "start_url":      "https://www.sslproxies.org/",
        "row_sel":        "table tbody tr",
        "ip_col":         0,
        "port_col":       1,
        "type_col":       6,
        "https_values":   ["yes"],
        "next_page_sel":  None,
        "max_pages":      1,
    },
    {
        "name":           "hidemy.name (page 1-3)",
        "start_url":      "https://hidemy.name/en/proxy-list/",
        "row_sel":        "table.proxy__t tbody tr",
        "ip_col":         0,
        "port_col":       1,
        "type_col":       4,
        "https_values":   ["HTTPS", "HTTP, HTTPS"],
        # пример пагинации — ссылка «следующая страница»
        "next_page_sel":  "li.next a",
        "max_pages":      3,
    },
]

# Прямые ссылки на текстовые файлы IP:PORT
FILE_SOURCES = [
    {
        "name":       "ProxyScrape — HTTP",
        "url":        "https://api.proxyscrape.com/v2/?request=displayproxies"
                      "&protocol=http&timeout=10000&country=all",
        "proxy_type": "HTTP",
    },
    {
        "name":       "ProxyScrape — SOCKS5",
        "url":        "https://api.proxyscrape.com/v2/?request=displayproxies"
                      "&protocol=socks5&timeout=10000&country=all",
        "proxy_type": "SOCKS5",
    },
    {
        "name":       "ProxyScrape — SOCKS4",
        "url":        "https://api.proxyscrape.com/v2/?request=displayproxies"
                      "&protocol=socks4&timeout=10000&country=all",
        "proxy_type": "SOCKS4",
    },
    {
        "name":       "GitHub TheSpeedX — HTTP",
        "url":        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "proxy_type": "HTTP",
    },
    {
        "name":       "GitHub TheSpeedX — SOCKS5",
        "url":        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "proxy_type": "SOCKS5",
    },
    {
        "name":       "GitHub TheSpeedX — SOCKS4",
        "url":        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "proxy_type": "SOCKS4",
    },
    # ── Additional SOCKS5 sources (prioritised — support HTTPS tunnelling) ──
    {
        "name":       "ProxyScrape v3 — SOCKS5",
        "url":        "https://api.proxyscrape.com/v3/free-proxy-list/get"
                      "?request=displayproxies&protocol=socks5&timeout=3000&limit=300",
        "proxy_type": "SOCKS5",
    },
    {
        "name":       "Monosans — SOCKS5",
        "url":        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "proxy_type": "SOCKS5",
    },
    {
        "name":       "Hookzof — SOCKS5",
        "url":        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "proxy_type": "SOCKS5",
    },
    {
        "name":       "B4RC0DE — SOCKS5",
        "url":        "https://raw.githubusercontent.com/B4RC0DE-TM/proxy-list/main/SOCKS5.txt",
        "proxy_type": "SOCKS5",
    },
    {
        "name":       "Mertguvencli — mixed",
        "url":        "https://raw.githubusercontent.com/mertguvencli/http-proxy-list/main/proxy-list/data.txt",
        "proxy_type": "HTTP",
    },
    # ── Additional HTTP sources (fallback — HTTP-only sites) ─────────────────
    {
        "name":       "ProxyScrape v3 — HTTP Elite",
        "url":        "https://api.proxyscrape.com/v3/free-proxy-list/get"
                      "?request=displayproxies&protocol=http&timeout=3000&anonymity=elite&limit=200",
        "proxy_type": "HTTP",
    },
    {
        "name":       "Monosans — HTTP",
        "url":        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "proxy_type": "HTTP",
    },
]

# JSON API источники
API_SOURCES = [
    {
        "name":            "GeoNode API",
        "url":             "https://proxylist.geonode.com/api/proxy-list",
        "params":          {
            "limit": 200, "page": 1,
            "sort_by": "lastChecked", "sort_type": "desc",
            "protocols": "http,https",
        },
        "data_key":        "data",
        "ip_field":        "ip",
        "port_field":      "port",
        "protocols_field": "protocols",
        "max_pages":       3,
    },
]

# ─── Настройки пинга ─────────────────────────────────────────────────────────
PING_TIMEOUT    = 3      # секунды на попытку TCP-соединения
PING_WORKERS    = 40     # параллельных воркеров
REQUEST_TIMEOUT = 12     # таймаут HTTP-запроса к источнику

# ─── TTL-кэш ─────────────────────────────────────────────────────────────────
CACHE_TTL_HOURS = 6      # адреса старше этого значения перепроверяются заново
                         # 0 = отключить кэш (всегда собирать заново)

# ─── Парсер HTML ─────────────────────────────────────────────────────────────
def parse_html_source(src: dict) -> list:
    """Парсит HTML-таблицы прокси, поддерживает пагинацию."""
    proxies = []
    url = src["start_url"]
    page = 1

    while url and page <= src.get("max_pages", 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select(src["row_sel"])
            page_count = 0

            for row in rows:
                cells = row.find_all("td")
                if len(cells) <= max(src["ip_col"], src["port_col"]):
                    continue
                ip   = cells[src["ip_col"]].get_text(strip=True)
                port = cells[src["port_col"]].get_text(strip=True)
                if not re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip):
                    continue
                if not port.isdigit():
                    continue
                ptype = "HTTP"
                if len(cells) > src.get("type_col", 99):
                    val = cells[src["type_col"]].get_text(strip=True)
                    if val in src.get("https_values", []):
                        ptype = "HTTPS"
                proxies.append({"ip": ip, "port": int(port), "type": ptype})
                page_count += 1

            info(f"Страница {page}: +{page_count} адресов")

            # Переход на следующую страницу
            nxt_sel = src.get("next_page_sel")
            if nxt_sel:
                nxt = soup.select_one(nxt_sel)
                if nxt and nxt.get("href"):
                    href = nxt["href"]
                    if href.startswith("http"):
                        url = href
                    else:
                        from urllib.parse import urljoin
                        url = urljoin(src["start_url"], href)
                else:
                    url = None
            else:
                url = None

            page += 1
            time.sleep(0.5)   # вежливая пауза

        except Exception as e:
            warn(f"HTML [{src['name']}] стр.{page}: {e}")
            break

    return proxies


# ─── Парсер файлов (IP:PORT) ──────────────────────────────────────────────────
def download_file_source(src: dict) -> list:
    """Скачивает текстовый файл формата IP:PORT."""
    proxies = []
    try:
        resp = requests.get(src["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT)
        for line in resp.text.splitlines():
            line = line.strip()
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}:\d+$", line):
                ip, port = line.split(":")
                proxies.append({"ip": ip, "port": int(port), "type": src["proxy_type"]})
    except Exception as e:
        warn(f"FILE [{src['name']}]: {e}")
    return proxies


# ─── Парсер API ───────────────────────────────────────────────────────────────
def fetch_api_source(src: dict) -> list:
    """Получает список прокси через JSON API с пагинацией."""
    proxies = []
    params  = dict(src["params"])

    for page in range(1, src["max_pages"] + 1):
        params["page"] = page
        try:
            resp  = requests.get(src["url"], params=params,
                                 headers=HEADERS, timeout=REQUEST_TIMEOUT)
            data  = resp.json()
            items = data.get(src["data_key"], [])
            if not items:
                break
            for item in items:
                ip     = item.get(src["ip_field"], "")
                port   = item.get(src["port_field"], "")
                protos = item.get(src["protocols_field"], ["HTTP"])
                ptype  = protos[0].upper() if protos else "HTTP"
                if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", str(ip)):
                    proxies.append({"ip": ip, "port": int(port), "type": ptype})
            info(f"Страница {page}: +{len(items)} адресов")
            time.sleep(0.3)
        except Exception as e:
            warn(f"API [{src['name']}] стр.{page}: {e}")
            break

    return proxies


# ─── TCP-пинг ─────────────────────────────────────────────────────────────────
def tcp_ping(ip: str, port: int, timeout: float = PING_TIMEOUT):
    """Замеряет время TCP-соединения. Возвращает ms или None."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        t0 = time.time()
        s.connect((ip, port))
        ms = (time.time() - t0) * 1000
        s.close()
        return round(ms, 1)
    except Exception:
        return None


def check_proxy(proxy: dict) -> dict:
    """Запускает TCP-пинг и обновляет поля proxy."""
    ms = tcp_ping(proxy["ip"], proxy["port"])
    proxy["ping_ms"]    = ms
    proxy["status"]     = "alive" if ms is not None else "dead"
    proxy["checked_at"] = datetime.now(timezone.utc).isoformat()
    return proxy


# ─── TTL: загрузка кэша и разделение на свежие/устаревшие ────────────────────
def _load_cache() -> tuple[dict, list]:
    """
    Читает существующий proxy_list.json.
    Возвращает:
      fresh_by_key  — {ip:port → proxy} для адресов внутри TTL (не трогаем)
      stale         — список адресов, которые нужно перепроверить
    """
    if CACHE_TTL_HOURS == 0 or not os.path.exists(OUTPUT_FILE):
        return {}, []

    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            cached = json.load(f)
    except Exception:
        return {}, []

    now       = datetime.now(timezone.utc)
    fresh     = {}
    stale     = []

    for p in cached:
        key = f"{p['ip']}:{p['port']}"
        ts  = p.get("checked_at")
        if ts:
            try:
                checked = datetime.fromisoformat(ts)
                # Добавляем tzinfo если отсутствует (старые записи)
                if checked.tzinfo is None:
                    checked = checked.replace(tzinfo=timezone.utc)
                age_h = (now - checked).total_seconds() / 3600
                if age_h < CACHE_TTL_HOURS:
                    fresh[key] = p
                    continue
            except Exception:
                pass
        stale.append(p)

    return fresh, stale


def _ping_batch(proxies_to_check: list) -> list:
    """Параллельный TCP-пинг списка прокси. Возвращает только живые."""
    if not proxies_to_check:
        return []

    alive = []
    done  = 0
    BAR_W = 28

    with ThreadPoolExecutor(max_workers=PING_WORKERS) as ex:
        futures = {ex.submit(check_proxy, p): p for p in proxies_to_check}
        for fut in as_completed(futures):
            result = fut.result()
            done  += 1
            filled = int(BAR_W * done / max(len(proxies_to_check), 1))
            bar    = f"{G}{'█' * filled}{DIM}{'░' * (BAR_W - filled)}{RS}"
            pct    = done / len(proxies_to_check) * 100
            if result["status"] == "alive":
                alive.append(result)
            print(
                f"  [{bar}] {pct:5.1f}%  "
                f"{G}✔{RS} {len(alive):>4} живых  │  "
                f"проверено {done}/{len(proxies_to_check)}     ",
                end="\r", flush=True
            )
    print()
    return alive


# ─── Главная функция ──────────────────────────────────────────────────────────
def collect_all() -> list:
    banner()

    # ── Загрузка кэша ────────────────────────────────────────
    fresh_cache, stale_cache = _load_cache()

    if fresh_cache:
        ttl_str = f"{CACHE_TTL_HOURS}ч"
        print(f"  {C}Кэш найден{RS}  (TTL={ttl_str})")
        print(f"  {G}Свежих адресов (пропускаем):   {len(fresh_cache)}{RS}")
        print(f"  {Y}Устаревших (перепроверим):     {len(stale_cache)}{RS}\n")
    elif CACHE_TTL_HOURS > 0 and os.path.exists(OUTPUT_FILE):
        print(f"  {Y}Кэш полностью устарел — собираем заново.{RS}\n")
    else:
        print(f"  {DIM}Кэш отключён или файл отсутствует — полный сбор.{RS}\n")

    # Известные ключи (свежие) — не будем их добавлять повторно из источников
    known_fresh_keys = set(fresh_cache.keys())

    all_proxies = []
    total_steps = len(HTML_SOURCES) + len(FILE_SOURCES) + len(API_SOURCES)
    step = 0

    # ── 1. HTML ──────────────────────────────────────────────
    print(f"{B}━━━ HTML-парсинг ({'─'*32}){RS}")
    for src in HTML_SOURCES:
        step += 1
        step_msg(step, total_steps, f"HTML › {src['name']} …")
        found = parse_html_source(src)
        ok(f"{src['name']}: {G}{B}{len(found)}{RS} адресов")
        all_proxies.extend(found)

    # ── 2. Файловые URL ──────────────────────────────────────
    print(f"\n{B}━━━ Файловые источники ({'─'*26}){RS}")
    for src in FILE_SOURCES:
        step += 1
        step_msg(step, total_steps, f"FILE › {src['name']} …")
        found = download_file_source(src)
        ok(f"{src['name']}: {G}{B}{len(found)}{RS} адресов")
        all_proxies.extend(found)

    # ── 3. API ───────────────────────────────────────────────
    print(f"\n{B}━━━ API-источники ({'─'*30}){RS}")
    for src in API_SOURCES:
        step += 1
        step_msg(step, total_steps, f"API  › {src['name']} …")
        found = fetch_api_source(src)
        ok(f"{src['name']}: {G}{B}{len(found)}{RS} адресов")
        all_proxies.extend(found)

    # ── Дедупликация + отсев свежих из кэша ──────────────────
    seen, new_only = set(), []
    for p in all_proxies:
        key = f"{p['ip']}:{p['port']}"
        if key in seen:
            continue
        seen.add(key)
        if key not in known_fresh_keys:   # не трогаем свежие
            new_only.append(p)

    # Устаревшие из кэша тоже нужно перепроверить
    # (добавляем только те, которых нет среди новых)
    for p in stale_cache:
        key = f"{p['ip']}:{p['port']}"
        if key not in seen:
            seen.add(key)
            new_only.append(p)

    print(f"\n  Собрано из источников: {len(all_proxies)}")
    print(f"  Новых / устаревших для проверки: {C}{B}{len(new_only)}{RS}")
    print(f"  Свежих из кэша (без проверки):  {G}{B}{len(fresh_cache)}{RS}")

    # ── Пинг-проверка ────────────────────────────────────────
    if new_only:
        print(f"\n{B}━━━ TCP Ping-проверка ({len(new_only)} адресов) ━━━{RS}")
        print(f"  {DIM}Воркеры: {PING_WORKERS} │ Таймаут: {PING_TIMEOUT}с{RS}\n")
        newly_alive = _ping_batch(new_only)
    else:
        newly_alive = []
        print(f"\n  {DIM}Нечего проверять — все адреса свежие.{RS}")

    # ── Объединение: свежий кэш + новые живые ────────────────
    combined = list(fresh_cache.values()) + newly_alive
    combined.sort(key=lambda x: (x.get("ping_ms") or 9999))

    print(f"\n  {G}{B}Итого живых прокси: {len(combined)}{RS}  "
          f"{DIM}(кэш: {len(fresh_cache)}  +  новых: {len(newly_alive)}){RS}")
    if combined:
        best = combined[0]
        print(f"  Лучший пинг:  {G}{best.get('ping_ms')}ms{RS}  "
              f"({best['ip']}:{best['port']}  [{best['type']}])")

    # ── Сохранение ───────────────────────────────────────────
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)

    print(f"\n  {C}Сохранено → {OUTPUT_FILE}{RS}")
    print(f"  {DIM}TTL кэша: {CACHE_TTL_HOURS}ч  │  "
          f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RS}\n")
    return combined


if __name__ == "__main__":
    collect_all()
