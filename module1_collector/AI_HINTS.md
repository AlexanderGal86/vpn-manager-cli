# AI_HINTS — Module 1: Proxy Collector

> Этот файл — подсказки для AI-ассистентов, работающих с данным модулем.
> Описывает архитектуру, намерения, точки расширения и частые ловушки.

---

## Назначение модуля

`collector.py` собирает IP-адреса прокси-серверов из трёх типов источников,
проверяет их доступность через TCP-соединение и сохраняет живые адреса
в `output/proxy_list.json` с временными метками для TTL-кэша.

---

## Архитектура

```
collect_all()
├── _load_cache()          → разделяет existing JSON на fresh / stale
├── parse_html_source()    → BeautifulSoup парсинг таблиц + пагинация
├── download_file_source() → скачивание текстовых файлов IP:PORT
├── fetch_api_source()     → JSON API с постраничной загрузкой
├── дедупликация           → по ключу "ip:port"
└── _ping_batch()          → параллельный TCP-пинг (ThreadPoolExecutor)
    └── check_proxy()      → одна попытка TCP connect + запись времени
```

---

## Ключевые константы (настроить в начале файла)

| Константа | Значение | Назначение |
|---|---|---|
| `CACHE_TTL_HOURS` | 6 | Адреса старше N часов перепроверяются |
| `PING_TIMEOUT` | 3 | Секунд на одну TCP-попытку |
| `PING_WORKERS` | 40 | Параллельных потоков для пинга |
| `REQUEST_TIMEOUT` | 12 | Таймаут HTTP-запроса к источнику |

---

## Формат выходного файла

```json
[
  {
    "ip": "1.2.3.4",
    "port": 8080,
    "type": "HTTP",          // HTTP | HTTPS | SOCKS4 | SOCKS5
    "ping_ms": 120.5,
    "status": "alive",
    "checked_at": "2024-01-15T10:30:00+00:00"   // ISO 8601 UTC
  }
]
```

Файл **всегда отсортирован по `ping_ms` по возрастанию** (лучшие первые).
Только живые прокси (`status == "alive"`) попадают в файл.

---

## TTL-кэш: логика при повторном запуске

```
Есть output/proxy_list.json?
  ├── НЕТ → полный сбор и пинг
  └── ДА  → для каждого адреса:
        ├── checked_at < CACHE_TTL_HOURS часов назад → оставить как есть (fresh)
        └── иначе → перепроверить TCP-пингом (stale)
Новые адреса из источников, которых нет в кэше → всегда пингуются
Итог = fresh_cache + newly_alive (объединяются и пересортируются)
```

---

## Добавление нового источника

### HTML-источник
Добавь словарь в список `HTML_SOURCES`:
```python
{
    "name":          "example-proxy-site.com",
    "start_url":     "https://example-proxy-site.com/list/",
    "row_sel":       "table.proxy-table tbody tr",  # CSS-селектор строк
    "ip_col":        0,          # индекс колонки с IP
    "port_col":      1,          # индекс колонки с портом
    "type_col":      4,          # индекс колонки с типом (опционально)
    "https_values":  ["yes", "HTTPS"],  # значения, означающие HTTPS
    "next_page_sel": "a.next-page",     # None если нет пагинации
    "max_pages":     5,
}
```

### Файловый URL
```python
{
    "name":       "My List",
    "url":        "https://example.com/proxies.txt",
    "proxy_type": "SOCKS5",  # HTTP | HTTPS | SOCKS4 | SOCKS5
}
```

### API-источник
```python
{
    "name":            "My API",
    "url":             "https://api.example.com/proxies",
    "params":          {"limit": 100, "page": 1},
    "data_key":        "data",        # ключ массива в JSON-ответе
    "ip_field":        "ip",
    "port_field":      "port",
    "protocols_field": "protocols",  # поле с типом (список строк)
    "max_pages":       5,
}
```

---

## Частые ловушки

1. **`checked_at` без timezone** — старые записи могут не иметь `tzinfo`.
   Код уже обрабатывает это: `checked.replace(tzinfo=timezone.utc)`.
   При изменении — не сломай эту логику.

2. **BeautifulSoup lxml vs html.parser** — используем `lxml` (быстрее).
   Если `lxml` не установлен → `ImportError`. Установи через `requirements.txt`.

3. **TCP-пинг ≠ HTTP-доступность** — прокси может принимать TCP-соединение
   но не быть рабочим HTTP-прокси. Финальная проверка скорости — в Module 2.

4. **PING_WORKERS > 100** — может вызвать ошибку "Too many open files" на Linux.
   Безопасный максимум: 60–80.

5. **Сайты с Cloudflare** — некоторые источники заблокируют scraping.
   Обновляй `User-Agent` в `HEADERS` при проблемах.

---

## Зависимости

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

Стандартные библиотеки: `socket`, `concurrent.futures`, `json`, `re`, `time`

---

## Интеграция с Module 2

Module 2 читает `module1_collector/output/proxy_list.json`.
Путь захардкожен относительно расположения `tester.py`:
```python
INPUT_FILE = os.path.join(BASE_DIR, "..", "module1_collector", "output", "proxy_list.json")
```
Не переименовывай выходной файл без правки `tester.py`.
