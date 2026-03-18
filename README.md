# VPN / Proxy Manager

> CLI-инструмент для автоматического сбора, проверки скорости и подключения прокси-серверов на Windows.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%2B-informational?logo=windows)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## Что это

Три независимых CLI-модуля, объединённых в pipeline:

```
[Module 1: Collector] ──proxy_list.json──▶ [Module 2: Tester] ──viable_proxies.json──▶ [Module 3: Connector]
    Сбор IP из                                  Тест скорости                              Системный прокси
  открытых источников                        батчами по 10, 2                              Windows + CLI
  HTML / файлы / API                         параллельно, TTL                                  меню
```

---

## Быстрый старт

### Вариант А — BAT (нужен Python)

```
Скачать dist/setup.bat → двойной клик
```

### Вариант Б — EXE (ничего не нужно)

```
1. Скачать dist/build_exe_source.py и dist/build_exe_on_windows.bat
2. Запустить build_exe_on_windows.bat
3. Запустить dist/VPN-Manager-Setup.exe
```

### Вариант В — из исходников

```bash
git clone https://github.com/<username>/vpn-manager.git
cd vpn-manager
pip install -r requirements.txt

python main.py              # полный pipeline: 1 → 2 → 3
python main.py --module 1   # только сбор
python main.py --module 2   # только тест скорости
python main.py --module 3   # только подключение
```

---

## Структура проекта

```
vpn-manager/
├── main.py                            ← pipeline + argparse CLI
├── requirements.txt
├── README.md
├── CHANGELOG.md                       ← история версий
├── DEVLOG.md                          ← журнал разработки
│
├── module1_collector/
│   ├── collector.py                   ← сбор прокси
│   ├── AI_HINTS.md                    ← подсказки для AI-ассистентов
│   └── output/
│       └── proxy_list.json            ← выход модуля
│
├── module2_tester/
│   ├── tester.py                      ← тест скорости
│   ├── AI_HINTS.md
│   └── output/
│       └── viable_proxies.json        ← выход модуля
│
├── module3_connector/
│   ├── connector.py                   ← системный прокси Windows
│   ├── AI_HINTS.md
│   └── output/
│       └── connection_log.txt         ← лог подключений
│
└── dist/
    ├── setup.bat                      ← самораспаковывающийся BAT (95 КБ)
    ├── build_exe_source.py            ← исходник для сборки EXE
    └── build_exe_on_windows.bat       ← сборка EXE на Windows
```

---

## Модули подробнее

### Module 1 — Collector

Собирает прокси из 10 источников трёх типов:

| Тип | Источники |
|---|---|
| HTML-парсинг | free-proxy-list.net, sslproxies.org, hidemy.name |
| Файловые URL | ProxyScrape (HTTP/SOCKS4/SOCKS5), GitHub TheSpeedX |
| JSON API | GeoNode с пагинацией |

**Возможности:**
- Пагинация HTML-страниц через CSS-селекторы
- Параллельный TCP ping-тест (40 воркеров)
- **TTL-кэш** — адреса свежее 6 часов не перепроверяются
- Прогресс-бар в CLI в реальном времени

**Выход:** `proxy_list.json` — отсортирован по пингу, только живые адреса.

---

### Module 2 — Tester

| Параметр | Значение |
|---|---|
| Размер батча | 10 прокси |
| Параллельность | 2 одновременно |
| Тест скорости | скачивание 2 МБ через прокси |
| Минимум для YouTube | 5 Мбит/с |
| Цель | 5 подходящих прокси |

**Умный перезапуск:**
- Свежие viable (< 3 часов) — не перетестируются
- Счётчик неудач: 3 провала подряд → автоудаление

---

### Module 3 — Connector

Устанавливает системный прокси Windows тремя методами с fallback:

```
winreg (реестр) → PowerShell → netsh winhttp
```

**Команды меню:**

| Ввод | Действие |
|---|---|
| `1`..`N` | Подключить выбранный прокси |
| `0` | Отключить прокси |
| `s` | Показать текущий статус |
| `q` | Выход |

> ⚠️ Модуль 3 требует **запуска от имени администратора** для записи в реестр Windows.

---

## Настройка

Все параметры — константы в начале каждого файла:

```python
# collector.py
CACHE_TTL_HOURS = 6      # TTL кэша (0 = отключить)
PING_WORKERS    = 40     # параллельных воркеров
PING_TIMEOUT    = 3      # секунд на TCP-попытку

# tester.py
MIN_SPEED_MBPS   = 5.0   # минимум для YouTube
RETEST_TTL_HOURS = 3     # TTL перепроверки
FAIL_EVICT_COUNT = 3     # неудач до удаления

# tester.py — пороги YouTube
# SD 480p:  ~2 Мбит/с
# HD 720p:  ~2.5 Мбит/с
# HD 1080p: ~5 Мбит/с  ← текущий порог
# 4K:       ~20 Мбит/с
```

---

## Требования

- Python 3.10+
- Windows 10/11 (для Module 3)
- Модули 1 и 2 работают на Linux/macOS

```
pip install -r requirements.txt
# requests, beautifulsoup4, lxml, PySocks
```

---

## AI-подсказки

Каждый модуль содержит `AI_HINTS.md` — документацию для AI-ассистентов:
архитектура, форматы данных, точки расширения, частые ловушки.

---

## Лицензия

MIT — используйте свободно. Соблюдайте законодательство своей страны.
