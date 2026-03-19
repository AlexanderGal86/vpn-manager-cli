# AI_HINTS — Module 2: Speed Tester

Hints for AI assistants working with this module.
Covers architecture, intent, extension points, and common pitfalls.

---

## Purpose

`tester.py` takes the list of live proxies from Module 1, tests real-world
download speed through each proxy, filters by a minimum YouTube threshold,
and saves suitable proxies to `output/viable_proxies.json`. On re-run it
reuses fresh results and auto-evicts unreliable proxies.

---

## Architecture

```
find_viable()
├── _load_viable()          -> reads existing viable_proxies.json
├── _is_stale()             -> checks TTL against tested_at field
├── split all_proxies       -> fresh_viable (skip) / to_test (test)
├── early exit              -> if fresh_viable >= TARGET_VIABLE, skip testing
├── run_batch()             -> process 10 at a time, 2 in parallel
│   ├── print_batch_header()
│   └── test_proxy() x N   -> latency check + speed download
├── _evict_failures()       -> removes proxies with fail_count >= FAIL_EVICT_COUNT
└── _save_and_print()       -> result table + write JSON
```

---

## Key constants (edit at top of file)

| Constant | Default | Purpose |
|---|---|---|
| `BATCH_SIZE` | 10 | Proxies per batch |
| `PARALLEL_TESTS` | 2 | Simultaneous tests within a batch |
| `MIN_SPEED_MBPS` | 5.0 | Minimum speed (YouTube HD threshold) |
| `TARGET_VIABLE` | 5 | Stop after finding this many viable proxies |
| `SPEED_TIMEOUT` | 20 | Seconds for the full speed download |
| `LATENCY_TIMEOUT` | 5 | Seconds for the latency HEAD request |
| `TEST_BYTES` | 2_097_152 | Bytes to download per test (2 MB) |
| `RETEST_TTL_HOURS` | 3 | Re-test proxies older than N hours |
| `FAIL_EVICT_COUNT` | 3 | Remove after N consecutive failures (0 = never) |

---

## Output file format

```json
[
  {
    "ip": "1.2.3.4",
    "port": 1080,
    "type": "SOCKS5",
    "speed_mbps": 8.32,
    "latency_ms": 95,
    "test_status": "ok",
    "tested_at": "2025-03-18T10:30:00+00:00",
    "fail_count": 0,
    "ping_ms": 120.5
  }
]
```

- `test_status`: `"ok"` or `"fail"`
- `fail_count`: consecutive failure count; resets to 0 on success
- `ping_ms`: inherited from Module 1 output
- File is **sorted by `speed_mbps` descending** (fastest first)

---

## Re-run logic

```
Load viable_proxies.json (existing_viable)
For each proxy in proxy_list.json:
  - exists in existing_viable AND tested_at < RETEST_TTL_HOURS ago
      -> fresh_viable (skip, keep as-is)
  - otherwise
      -> to_test (run speed test)

After testing:
  - pass (speed >= MIN_SPEED_MBPS) -> fail_count = 0
  - fail                           -> fail_count += 1
      - fail_count >= FAIL_EVICT_COUNT -> REMOVE from viable list

Result = fresh_viable + new_viable - evicted
```

---

## Speed test algorithm

```python
# Stage 1: latency (HEAD request to a lightweight endpoint)
t0 = time.time()
requests.head("http://www.gstatic.com/generate_204",
              proxies=proxy_dict, timeout=LATENCY_TIMEOUT)
latency_ms = (time.time() - t0) * 1000

# Stage 2: speed (streaming download, stop after TEST_BYTES)
t1 = time.time()
resp = requests.get(TEST_URL, proxies=proxy_dict,
                    stream=True, timeout=SPEED_TIMEOUT)
downloaded = 0
for chunk in resp.iter_content(chunk_size=65536):
    downloaded += len(chunk)
    if downloaded >= TEST_BYTES:
        break
speed_mbps = (downloaded * 8) / ((time.time() - t1) * 1_000_000)
```

If the first `SPEED_TEST_URLS` entry fails, the next one is tried automatically.

---

## Proxy URL format for `requests`

```python
def proxy_dict(p):
    addr = f"{p['ip']}:{p['port']}"
    if p["type"] == "SOCKS5":  return {"http": f"socks5h://{addr}", "https": f"socks5h://{addr}"}
    if p["type"] == "SOCKS4":  return {"http": f"socks4://{addr}",  "https": f"socks4://{addr}"}
    else:                       return {"http": f"http://{addr}",    "https": f"http://{addr}"}
```

`socks5h://` routes DNS resolution through the proxy (important for anonymity).
Requires `PySocks` (`pip install PySocks`, already in `requirements.txt`).

---

## YouTube speed reference

| Quality | Bitrate |
|---|---|
| SD 480p | ~2 Mbit/s |
| HD 720p | ~2.5 Mbit/s |
| HD 1080p | ~5 Mbit/s ← default threshold |
| 4K | ~20 Mbit/s |

---

## Common pitfalls

**1. `requests` without `PySocks` installed**
SOCKS proxies raise `ValueError: SOCKSHTTPSConnectionPool(...)`.
Fix: `pip install PySocks` (already in `requirements.txt`).

**2. All SPEED_TEST_URLS blocked through the proxy**
All three fallback URLs may be unreachable through certain proxies.
If this is a persistent problem, add alternative URLs to `SPEED_TEST_URLS`.
Each URL must serve a file of at least `TEST_BYTES` bytes without auth.

**3. `threading.Lock` in `run_batch` — do not remove**
Progress display is updated from two concurrent threads.
Removing the lock causes interleaved writes and garbled output.

**4. `_is_stale` handles timezone-naive records**
```python
if tested.tzinfo is None:
    tested = tested.replace(tzinfo=timezone.utc)
```
Old records without timezone info are treated as UTC. Do not remove this guard.

**5. `TARGET_VIABLE` stops by count, not by batch**
The module stops as soon as `len(viable) >= TARGET_VIABLE`, even mid-batch.
To process exactly one batch regardless of results, set `TARGET_VIABLE = BATCH_SIZE`.

**6. Windows console output garbled**
Same fix as Module 1 — `sys.stdout.reconfigure(encoding="utf-8")` at startup.
Already present in the file. Do not remove.

**7. `fail_count` persists across sessions**
The `fail_count` field is written to JSON and read back on re-run.
A proxy evicted by `FAIL_EVICT_COUNT` will not reappear unless Module 1
re-collects it and it passes a fresh speed test.

---

## Extension: add a per-site reachability check

Add after the speed measurement block in `test_proxy()`:
```python
try:
    r = requests.get("https://www.youtube.com",
                     proxies=proxies, timeout=10)
    result["youtube_accessible"] = (r.status_code == 200)
except Exception:
    result["youtube_accessible"] = False
```

---

## Dependencies

```
requests>=2.31.0
PySocks>=1.7.1
```

Standard library: `concurrent.futures`, `threading`, `json`, `time`,
`datetime`, `timezone`

---

## Integration

- **Input**: `../module1_collector/output/proxy_list.json`
- **Output**: `output/viable_proxies.json` — read by Module 3
