# AI_HINTS — Module 1: Proxy Collector

Hints for AI assistants working with this module.
Covers architecture, intent, extension points, and common pitfalls.

---

## Purpose

`collector.py` gathers proxy IP addresses from three source types,
verifies reachability via TCP connect, and saves live addresses to
`output/proxy_list.json` with timestamps for TTL-based caching.

---

## Architecture

```
collect_all()
├── _load_cache()          -> splits existing JSON into fresh / stale buckets
├── parse_html_source()    -> BeautifulSoup table scraping + pagination
├── download_file_source() -> downloads IP:PORT text files line by line
├── fetch_api_source()     -> JSON API with page iteration
├── deduplication          -> by "ip:port" key; skips keys in fresh cache
└── _ping_batch()          -> parallel TCP ping (ThreadPoolExecutor)
    └── check_proxy()      -> single TCP connect attempt + writes checked_at
```

---

## Key constants (edit at top of file)

| Constant | Default | Purpose |
|---|---|---|
| `CACHE_TTL_HOURS` | 6 | Addresses older than N hours are re-pinged |
| `PING_TIMEOUT` | 3 | Seconds per TCP connect attempt |
| `PING_WORKERS` | 40 | Parallel worker threads |
| `REQUEST_TIMEOUT` | 12 | HTTP request timeout for source fetching |

---

## Output file format

```json
[
  {
    "ip": "1.2.3.4",
    "port": 8080,
    "type": "HTTP",
    "ping_ms": 120.5,
    "status": "alive",
    "checked_at": "2025-03-18T10:30:00+00:00"
  }
]
```

- `type` is one of: `HTTP`, `HTTPS`, `SOCKS4`, `SOCKS5`
- `checked_at` is always timezone-aware ISO 8601 UTC
- File is **sorted by `ping_ms` ascending** (fastest first)
- Only `status == "alive"` entries are written

---

## TTL cache logic on re-run

```
output/proxy_list.json exists?
  NO  -> full collect + ping all
  YES -> for each address:
           age < CACHE_TTL_HOURS  -> keep as-is (fresh)
           age >= CACHE_TTL_HOURS -> re-ping (stale)

New addresses from sources not in cache -> always pinged
Result = fresh_cache + newly_alive, merged and re-sorted by ping_ms
```

Setting `CACHE_TTL_HOURS = 0` disables the cache entirely (full overwrite
every run).

---

## Adding a new source

### HTML source — add a dict to `HTML_SOURCES`
```python
{
    "name":          "example-proxy-site.com",
    "start_url":     "https://example-proxy-site.com/list/",
    "row_sel":       "table.proxy-table tbody tr",  # CSS selector for rows
    "ip_col":        0,           # column index for IP
    "port_col":      1,           # column index for port
    "type_col":      4,           # column index for protocol (optional)
    "https_values":  ["yes", "HTTPS"],  # values that mean HTTPS
    "next_page_sel": "a.next-page",     # None if no pagination
    "max_pages":     5,
}
```

### File URL source — add a dict to `FILE_SOURCES`
```python
{
    "name":       "My List",
    "url":        "https://example.com/proxies.txt",
    "proxy_type": "SOCKS5",   # HTTP | HTTPS | SOCKS4 | SOCKS5
}
```

### API source — add a dict to `API_SOURCES`
```python
{
    "name":            "My API",
    "url":             "https://api.example.com/proxies",
    "params":          {"limit": 100, "page": 1},
    "data_key":        "data",        # key containing the list in JSON response
    "ip_field":        "ip",
    "port_field":      "port",
    "protocols_field": "protocols",   # field with protocol type (list of strings)
    "max_pages":       5,
}
```

---

## Common pitfalls

**1. `checked_at` without timezone (legacy records)**
Old records may lack `tzinfo`. Comparing a naive datetime with an aware one
raises `TypeError`. The code guards against this:
```python
if checked.tzinfo is None:
    checked = checked.replace(tzinfo=timezone.utc)
```
Do not remove this guard when modifying `_load_cache()`.

**2. Windows console output garbled**
All `print()` calls use UTF-8. On Windows, stdout defaults to cp866/cp1252.
The fix at module startup:
```python
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```
`errors="replace"` prevents crashes — outputs `?` for unencodable chars.
`SetConsoleMode` enables ANSI colours but does NOT change the encoding.
Both calls are required.

**3. BeautifulSoup: `lxml` vs `html.parser`**
`lxml` is used (faster). If not installed → `ImportError`.
Always install via `requirements.txt`, never skip it.

**4. TCP ping != HTTP proxy reachability**
A host may accept a TCP connection but not function as an HTTP proxy.
This pass-through is intentional — Module 2 does the real HTTP test.
Do not add HTTP checks here; it would multiply run time by 10×.

**5. `PING_WORKERS` above 100 on Linux**
May cause "Too many open files". Safe maximum: 60–80.
The default of 40 is conservative and works everywhere.

**6. Cloudflare-protected sources**
Some sites block automated requests. Symptoms: empty result or 403/503.
Update `User-Agent` in `HEADERS` to a recent browser string.
Consider rotating User-Agents for problematic sources.

**7. HTML sources break on site layout changes**
CSS selectors in `HTML_SOURCES` are brittle. If a source returns 0 rows,
the site likely changed its markup. Update `row_sel`, `ip_col`, etc.
This is the highest-priority maintenance task in the project.

---

## Dependencies

```
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
```

Standard library used: `socket`, `concurrent.futures`, `json`, `re`, `time`,
`datetime`, `timezone`

---

## Integration with Module 2

Module 2 reads `module1_collector/output/proxy_list.json`.
The path is hardcoded relative to `tester.py` location:
```python
INPUT_FILE = os.path.join(BASE_DIR, "..", "module1_collector", "output", "proxy_list.json")
```
Do not rename the output file without updating `tester.py`.
The `output/` directory must exist (tracked via `.gitkeep`).
