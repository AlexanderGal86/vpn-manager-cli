"""
MODULE 2 — SPEED TESTER
Берёт список от Модуля 1, тестирует скорость по 10 адресов (2 параллельно),
ищет прокси с достаточной скоростью для YouTube (≥5 Мбит/с).
Выход: module2_tester/output/viable_proxies.json
"""

import os
import sys
import json
import time
import socket
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# ─── Пути ────────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE  = os.path.join(BASE_DIR, "..", "module1_collector", "output", "proxy_list.json")
OUTPUT_DIR  = os.path.join(BASE_DIR, "output")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "viable_proxies.json")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── ANSI-цвета ──────────────────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleMode(
            ctypes.windll.kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass

G   = "\033[92m";  Y = "\033[93m";  R = "\033[91m"
C   = "\033[96m";  B = "\033[1m";   RS = "\033[0m";  DIM = "\033[2m"

# ─── Конфиг ───────────────────────────────────────────────────────────────────
BATCH_SIZE      = 10        # адресов в одном батче
PARALLEL_TESTS  = 2         # параллельных тестов
MIN_SPEED_MBPS  = 5.0       # минимум для YouTube
TARGET_VIABLE   = 5         # сколько найти и остановиться
SPEED_TIMEOUT   = 20        # секунд на весь тест скорости
LATENCY_TIMEOUT = 5         # секунд на замер задержки
TEST_BYTES      = 2_097_152 # сколько байт скачать (2 МБ)

# ─── Политика перезапуска ─────────────────────────────────────────────────────
RETEST_TTL_HOURS  = 3    # перепроверять прокси, которые тестировались > N часов назад
FAIL_EVICT_COUNT  = 3    # удалить прокси из viable_proxies.json если не прошёл
                         # тест скорости N раз подряд (0 = не удалять автоматически)

# Тестовые URL (пробуем по очереди)
SPEED_TEST_URLS = [
    "http://speedtest.tele2.net/1MB.zip",
    "http://ipv4.download.thinkbroadband.com/1MB.zip",
    "http://speedtest.ftp.otenet.gr/files/test1Mb.db",
]

LATENCY_URL = "http://www.gstatic.com/generate_204"   # лёгкий эндпоинт Google

# ─── Хелперы вывода ──────────────────────────────────────────────────────────
def banner():
    print(f"""
{C}{B}╔══════════════════════════════════════════════╗
║   MODULE 2 — SPEED TESTER                    ║
║   Поиск быстрых прокси для YouTube           ║
╚══════════════════════════════════════════════╝{RS}
""")

def sep(char="─", width=54):
    print(f"  {DIM}{char * width}{RS}")

# ─── Формирование прокси-URL для requests ────────────────────────────────────
def proxy_dict(p: dict) -> dict:
    ptype = p["type"].lower()
    addr  = f"{p['ip']}:{p['port']}"
    if ptype == "socks5":
        url = f"socks5h://{addr}"
    elif ptype == "socks4":
        url = f"socks4://{addr}"
    else:
        url = f"http://{addr}"
    return {"http": url, "https": url}


# ─── Тест скорости ────────────────────────────────────────────────────────────
def test_proxy(p: dict) -> dict:
    """
    Проверяет прокси:
      1) Замер задержки (HEAD к LATENCY_URL)
      2) Замер скорости (скачивание TEST_BYTES)
    Возвращает обновлённый словарь.
    """
    result = {
        **p,
        "speed_mbps":  0.0,
        "latency_ms":  None,
        "test_status": "fail",
        "tested_at":   datetime.now(timezone.utc).isoformat(),
    }
    proxies = proxy_dict(p)

    # — Задержка ——————————————————————————————————————————————
    try:
        t0 = time.time()
        requests.head(LATENCY_URL, proxies=proxies,
                      timeout=LATENCY_TIMEOUT, allow_redirects=True)
        result["latency_ms"] = round((time.time() - t0) * 1000)
    except Exception as e:
        result["error"] = f"latency: {str(e)[:60]}"
        return result   # если нет связи — не проверяем скорость

    # — Скорость ——————————————————————————————————————————————
    for test_url in SPEED_TEST_URLS:
        try:
            t1 = time.time()
            resp = requests.get(
                test_url, proxies=proxies,
                stream=True, timeout=SPEED_TIMEOUT
            )
            downloaded = 0
            for chunk in resp.iter_content(chunk_size=65536):
                downloaded += len(chunk)
                if downloaded >= TEST_BYTES:
                    break
            elapsed = time.time() - t1
            if elapsed > 0 and downloaded > 0:
                result["speed_mbps"]  = round((downloaded * 8) / (elapsed * 1_000_000), 2)
                result["test_status"] = "ok"
                break   # успешно — не пробуем следующий URL
        except Exception as e:
            result["error"] = f"speed: {str(e)[:60]}"
            continue   # пробуем следующий тестовый URL

    return result


# ─── Вывод заголовка батча ───────────────────────────────────────────────────
def print_batch_header(batch_num: int, total_checked: int, proxies: list):
    start = total_checked + 1
    end   = total_checked + len(proxies)
    print(f"\n{B}  ┌{'─'*52}┐{RS}")
    print(f"{B}  │  Batch #{batch_num}  —  адреса {start}–{end}{' '*(43 - len(str(start)) - len(str(end)))}│{RS}")
    print(f"{B}  └{'─'*52}┘{RS}")
    for i, p in enumerate(proxies):
        idx   = total_checked + i + 1
        ping  = f"{p.get('ping_ms', '?')}ms" if p.get("ping_ms") else "?"
        print(f"    {DIM}{idx:>3}.{RS}  "
              f"{p['ip']:15}:{p['port']:<5}  "
              f"[{p['type']:<6}]  "
              f"ping {ping}")
    sep()
    print(f"    {DIM}Тестируем по {PARALLEL_TESTS} прокси одновременно "
          f"│ порог скорости: {MIN_SPEED_MBPS} Мбит/с{RS}")
    sep()


# ─── Запуск батча ────────────────────────────────────────────────────────────
def run_batch(batch_num: int, total_checked: int, proxies: list) -> list:
    """
    Тестирует список proxies по PARALLEL_TESTS штуки за раз.
    Возвращает все результаты (успешные и нет).
    """
    print_batch_header(batch_num, total_checked, proxies)
    all_results = []

    for sub_start in range(0, len(proxies), PARALLEL_TESTS):
        sub  = proxies[sub_start:sub_start + PARALLEL_TESTS]
        pair = "  ".join(f"{p['ip']}:{p['port']}" for p in sub)
        print(f"\n    {C}→ Пара {sub_start // PARALLEL_TESTS + 1}:{RS}  {pair}")

        # Индикаторы прогресса для пары
        progress = {p["ip"]: "…" for p in sub}
        lock = threading.Lock()

        def _update_line():
            parts = []
            for p in sub:
                ip_str = f"{p['ip']:15}:{p['port']:<5}"
                tag    = progress.get(p["ip"], "…")
                parts.append(f"  {ip_str}  {tag}")
            print("      " + "  │  ".join(parts), end="\r", flush=True)

        _update_line()

        with ThreadPoolExecutor(max_workers=PARALLEL_TESTS) as ex:
            futs = {ex.submit(test_proxy, p): p for p in sub}
            for fut in as_completed(futs):
                r   = fut.result()
                spd = r["speed_mbps"]
                lat = r.get("latency_ms")
                lat_str = f"{lat}ms" if lat else "timeout"

                if r["test_status"] == "fail":
                    tag = f"{R}✖ недоступен{RS}"
                elif spd >= MIN_SPEED_MBPS:
                    tag = f"{G}✔ {spd:.2f} Мбит/с  lat:{lat_str}{RS}"
                elif spd > 0:
                    tag = f"{Y}~ {spd:.2f} Мбит/с  lat:{lat_str}{RS}"
                else:
                    tag = f"{R}✖ 0 Мбит/с{RS}"

                with lock:
                    progress[r["ip"]] = tag
                    _update_line()

                all_results.append(r)

        print()  # перевод строки после \r

    viable_in_batch = [r for r in all_results if r["speed_mbps"] >= MIN_SPEED_MBPS]
    print(f"\n    {G}Подходящих в этом batch: {len(viable_in_batch)}{RS}")
    return all_results


# ─── Загрузка существующих viable-прокси ─────────────────────────────────────
def _load_viable() -> list:
    if not os.path.exists(OUTPUT_FILE):
        return []
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _is_stale(proxy: dict) -> bool:
    """True если прокси нужно перепроверить (TTL истёк или нет метки времени)."""
    if RETEST_TTL_HOURS == 0:
        return True
    ts = proxy.get("tested_at")
    if not ts:
        return True
    try:
        tested = datetime.fromisoformat(ts)
        if tested.tzinfo is None:
            tested = tested.replace(tzinfo=timezone.utc)
        age_h = (datetime.now(timezone.utc) - tested).total_seconds() / 3600
        return age_h >= RETEST_TTL_HOURS
    except Exception:
        return True


def _evict_failures(viable: list, new_results: dict) -> tuple[list, int]:
    """
    Удаляет прокси из viable-списка если счётчик неудач достиг FAIL_EVICT_COUNT.
    new_results: {ip:port → result dict}
    Возвращает (обновлённый список, количество удалённых).
    """
    if FAIL_EVICT_COUNT == 0:
        return viable, 0

    evicted = 0
    kept = []
    for p in viable:
        key = f"{p['ip']}:{p['port']}"
        r   = new_results.get(key)
        if r and r["test_status"] != "ok":
            fails = p.get("fail_count", 0) + 1
            if fails >= FAIL_EVICT_COUNT:
                evicted += 1
                continue  # удаляем
            p["fail_count"] = fails
        elif r and r["test_status"] == "ok":
            p["fail_count"] = 0   # сбрасываем счётчик при успехе
        kept.append(p)

    return kept, evicted


# ─── Главная функция ─────────────────────────────────────────────────────────
def find_viable() -> list:
    banner()

    # Загрузка proxy_list от Модуля 1
    if not os.path.exists(INPUT_FILE):
        print(f"  {R}Файл не найден: {INPUT_FILE}{RS}")
        print(f"  {Y}Сначала запустите Модуль 1 (collector.py){RS}\n")
        sys.exit(1)

    with open(INPUT_FILE, encoding="utf-8") as f:
        all_proxies = json.load(f)

    if not all_proxies:
        print(f"  {R}Список прокси пуст. Запустите Модуль 1 повторно.{RS}\n")
        sys.exit(1)

    # Загрузка существующих viable
    existing_viable = _load_viable()
    existing_by_key = {f"{p['ip']}:{p['port']}": p for p in existing_viable}

    # Разбиваем all_proxies на: нужно тестировать / уже свежие в viable
    fresh_viable    = {}   # ключ → прокси (не трогаем)
    to_test         = []   # нужно протестировать

    for p in all_proxies:
        key = f"{p['ip']}:{p['port']}"
        if key in existing_by_key:
            ev = existing_by_key[key]
            if not _is_stale(ev):
                fresh_viable[key] = ev   # свежий — оставляем
                continue
            else:
                # Устаревший — перетестируем, сохраняем fail_count
                p["fail_count"] = ev.get("fail_count", 0)
        to_test.append(p)

    retest_viable = [p for p in to_test
                     if f"{p['ip']}:{p['port']}" in existing_by_key]

    print(f"  Загружено прокси:               {C}{B}{len(all_proxies)}{RS}")
    print(f"  Минимальная скорость:           {C}{B}{MIN_SPEED_MBPS} Мбит/с{RS}  (YouTube SD/HD)")
    print(f"  Цель — найти не менее:          {C}{B}{TARGET_VIABLE}{RS} подходящих")
    print(f"  Свежих viable (пропускаем):     {G}{B}{len(fresh_viable)}{RS}")
    print(f"  Перепроверяем устаревших viable:{Y}{B} {len(retest_viable)}{RS}")
    print(f"  Новых для теста:                {C}{B}{len(to_test) - len(retest_viable)}{RS}\n")

    # Если fresh_viable уже достаточно — сразу выходим
    if len(fresh_viable) >= TARGET_VIABLE:
        print(f"  {G}Достаточно свежих прокси в кэше ({len(fresh_viable)}) — тестирование не нужно.{RS}")
        final = sorted(fresh_viable.values(), key=lambda x: x["speed_mbps"], reverse=True)
        _save_and_print(final)
        return final

    viable        = list(fresh_viable.values())
    batch_num     = 0
    total_checked = 0
    new_results   = {}   # ключ → результат (для счётчика неудач)

    for start in range(0, len(to_test), BATCH_SIZE):
        batch      = to_test[start:start + BATCH_SIZE]
        batch_num += 1

        results = run_batch(batch_num, total_checked, batch)
        total_checked += len(batch)

        for r in results:
            key = f"{r['ip']}:{r['port']}"
            new_results[key] = r

        new_viable = [r for r in results if r["speed_mbps"] >= MIN_SPEED_MBPS]
        viable.extend(new_viable)

        print(f"    {DIM}Всего подходящих: {len(viable)} / нужно: {TARGET_VIABLE}{RS}")

        if len(viable) >= TARGET_VIABLE:
            print(f"\n  {G}{B}Найдено {len(viable)} подходящих прокси — останавливаемся.{RS}")
            break
        if start + BATCH_SIZE < len(to_test):
            print(f"\n  {DIM}Переходим к следующему батчу…{RS}")

    # ── Эвикция провалившихся ─────────────────────────────────
    if FAIL_EVICT_COUNT > 0 and new_results:
        viable, evicted = _evict_failures(viable, new_results)
        if evicted:
            print(f"\n  {Y}Удалено ненадёжных прокси: {evicted} "
                  f"(провалили тест {FAIL_EVICT_COUNT}+ раз подряд){RS}")

    return _save_and_print(viable)


def _save_and_print(viable: list) -> list:
    """Выводит итоговую таблицу и сохраняет viable_proxies.json."""
    print(f"\n{'═'*56}")
    if not viable:
        print(f"  {Y}Подходящих прокси не найдено.")
        print(f"  Попробуйте повторно запустить Модуль 1 для обновления списка.{RS}")
        return []

    viable = sorted(viable, key=lambda x: x["speed_mbps"], reverse=True)

    print(f"  {G}{B}РЕЗУЛЬТАТ — {len(viable)} подходящих прокси:{RS}")
    print(f"{'═'*56}")
    print(f"  {'№':>3}  {'IP:Порт':<22}  {'Тип':<6}  {'Скорость':>10}  {'Задержка':>9}  {'Неудач':>6}")
    print(f"  {'─'*60}")
    for i, p in enumerate(viable):
        spd   = f"{p['speed_mbps']:.2f} Мбит/с"
        lat   = f"{p.get('latency_ms', '?')} ms"
        fails = p.get('fail_count', 0)
        fail_tag = f"{Y}{fails}{RS}" if fails > 0 else f"{DIM}0{RS}"
        print(f"  {C}{i+1:>3}.{RS}  "
              f"{p['ip']}:{p['port']:<5}  "
              f"[{p['type']:<6}]  "
              f"{G}{spd:>10}{RS}  "
              f"{lat:>9}  "
              f"  {fail_tag:>6}")
    print(f"{'═'*56}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(viable, f, indent=2, ensure_ascii=False)
    print(f"\n  {C}Сохранено → {OUTPUT_FILE}{RS}")
    print(f"  {DIM}Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RS}\n")
    return viable


if __name__ == "__main__":
    find_viable()
