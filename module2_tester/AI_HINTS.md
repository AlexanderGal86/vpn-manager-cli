# AI_HINTS — Module 2: Speed Tester

> Этот файл — подсказки для AI-ассистентов, работающих с данным модулем.
> Описывает архитектуру, намерения, точки расширения и частые ловушки.

---

## Назначение модуля

`tester.py` берёт список живых прокси от Module 1, проверяет реальную
скорость работы через каждый прокси (скачивание тестового файла),
фильтрует по минимальному порогу YouTube и сохраняет пригодные
в `output/viable_proxies.json`. При повторном запуске умеет переиспользовать
свежие результаты и удалять ненадёжные прокси автоматически.

---

## Архитектура

```
find_viable()
├── _load_viable()          → читает существующий viable_proxies.json
├── _is_stale()             → проверяет TTL по полю tested_at
├── разделение all_proxies  → fresh_viable (пропустить) / to_test (проверить)
├── run_batch()             → батч из 10, по 2 параллельно
│   ├── print_batch_header()
│   └── test_proxy() × N   → замер задержки + скачивание
├── _evict_failures()       → удаляет прокси с fail_count >= FAIL_EVICT_COUNT
└── _save_and_print()       → таблица + запись JSON
```

---

## Ключевые константы

| Константа | Значение | Назначение |
|---|---|---|
| `BATCH_SIZE` | 10 | Прокси в одном батче |
| `PARALLEL_TESTS` | 2 | Параллельных тестов внутри батча |
| `MIN_SPEED_MBPS` | 5.0 | Минимум для YouTube (SD ~2, HD ~5, 4K ~20) |
| `TARGET_VIABLE` | 5 | Сколько найти и остановиться |
| `SPEED_TIMEOUT` | 20 | Секунд на тест скорости |
| `LATENCY_TIMEOUT` | 5 | Секунд на замер задержки |
| `TEST_BYTES` | 2_097_152 | Сколько байт скачивать (2 МБ) |
| `RETEST_TTL_HOURS` | 3 | Перепроверять прокси старше N часов |
| `FAIL_EVICT_COUNT` | 3 | Удалить после N неудач подряд (0 = отключить) |

---

## Формат выходного файла

```json
[
  {
    "ip": "1.2.3.4",
    "port": 1080,
    "type": "SOCKS5",
    "speed_mbps": 8.32,
    "latency_ms": 95,
    "test_status": "ok",           // "ok" | "fail"
    "tested_at": "2024-01-15T10:30:00+00:00",
    "fail_count": 0,               // счётчик неудач подряд
    "ping_ms": 120.5               // унаследовано от Module 1
  }
]
```

Файл **отсортирован по `speed_mbps` по убыванию** (быстрые первые).

---

## Логика повторного запуска

```
Загрузить viable_proxies.json (existing_viable)
Для каждого прокси из proxy_list.json:
  ├── Есть в existing_viable И tested_at < RETEST_TTL_HOURS → fresh_viable (пропустить)
  └── иначе → to_test (тестировать)

После тестирования:
  ├── Успех (speed >= MIN_SPEED_MBPS) → fail_count = 0
  └── Провал → fail_count += 1
      └── fail_count >= FAIL_EVICT_COUNT → УДАЛИТЬ из viable

Итог = fresh_viable + новые viable - evicted
```

---

## Алгоритм теста скорости

```python
# 1. Замер задержки (HEAD запрос к Google)
t0 = time.time()
requests.head("http://www.gstatic.com/generate_204", proxies=proxy_dict, timeout=5)
latency_ms = (time.time() - t0) * 1000

# 2. Замер скорости (скачивание 2МБ через прокси)
t1 = time.time()
resp = requests.get(TEST_URL, proxies=proxy_dict, stream=True, timeout=20)
downloaded = 0
for chunk in resp.iter_content(chunk_size=65536):
    downloaded += len(chunk)
    if downloaded >= TEST_BYTES: break
speed_mbps = (downloaded * 8) / ((time.time() - t1) * 1_000_000)
```

Fallback: если первый тестовый URL недоступен — пробует следующий из `SPEED_TEST_URLS`.

---

## Формат прокси-URL для requests

```python
def proxy_dict(p):
    if p["type"] in ("SOCKS5",):  return {"http": f"socks5h://{ip}:{port}", ...}
    if p["type"] in ("SOCKS4",):  return {"http": f"socks4://{ip}:{port}",  ...}
    else:                          return {"http": f"http://{ip}:{port}",    ...}
```

`socks5h://` — резолвинг DNS через прокси (важно для анонимности).
Требует библиотеку `PySocks` (`pip install PySocks`).

---

## Частые ловушки

1. **`requests` без `PySocks`** — SOCKS-прокси вызовут `ValueError: SOCKSHTTPSConnectionPool`.
   Решение: `pip install PySocks` (уже в requirements.txt).

2. **SPEED_TEST_URLS недоступны** — все три URL могут быть заблокированы через прокси.
   При необходимости добавь свои URL в список. Файл должен быть ≥ TEST_BYTES.

3. **`threading.Lock` в `run_batch`** — обновление прогресса идёт из нескольких потоков.
   Не убирай Lock при модификации print-логики.

4. **`_is_stale` без tzinfo** — старые записи без timezone обрабатываются:
   `tested.replace(tzinfo=timezone.utc)`. Не удаляй эту строку.

5. **TARGET_VIABLE** — остановка по количеству, а не по батчам.
   Если нужна остановка после первого батча — уменьши до BATCH_SIZE.

---

## Расширение: другие метрики

Чтобы добавить проверку конкретного сайта (например, youtube.com):
```python
# В test_proxy() после замера скорости:
try:
    r = requests.get("https://www.youtube.com", proxies=proxies, timeout=10)
    result["youtube_accessible"] = r.status_code == 200
except:
    result["youtube_accessible"] = False
```

---

## Зависимости

```
requests>=2.31.0
PySocks>=1.7.1
```

Стандартные: `concurrent.futures`, `threading`, `json`, `time`, `socket`

---

## Интеграция

- **Вход**: `../module1_collector/output/proxy_list.json`
- **Выход**: `output/viable_proxies.json` → читается Module 3
