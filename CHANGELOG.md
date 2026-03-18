# CHANGELOG — VPN / Proxy Manager

Все значимые изменения проекта документируются здесь.
Формат основан на [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.2.0] — 2025-03-18 · Дистрибутивы Windows

### Added
- `dist/setup.bat` — самораспаковывающийся BAT-файл (95 КБ)
  - Проверка прав администратора с автоматическим перезапуском через UAC
  - Проверка наличия Python; предложение установить через `winget` или python.org
  - Встроенный архив проекта в base64; декодирование через PowerShell
  - Создание временного файла во `%TEMP%` с последующей очисткой
- `dist/build_exe_source.py` — исходник для сборки standalone EXE через PyInstaller
  - Встроенный архив проекта
  - Выбор папки установки (по умолчанию `~/vpn-manager`)
  - Создание ярлыка `VPN Manager.bat` на рабочем столе
  - Перезапуск от имени администратора через `ShellExecuteW`
- `dist/build_exe_on_windows.bat` — скрипт для сборки EXE на Windows-машине пользователя

### Notes
- EXE не собирается на Linux/macOS — только через PyInstaller на Windows
- Размер standalone EXE ~7 МБ (включает Python runtime)

---

## [1.1.0] — 2025-03-18 · Умный перезапуск (TTL + счётчик неудач)

### Added — Module 1 (collector.py)
- **TTL-кэш** (`CACHE_TTL_HOURS = 6`):
  - При повторном запуске загружает существующий `proxy_list.json`
  - Адреса с `checked_at` моложе TTL — пропускаются (не перепингуются)
  - Адреса старше TTL или без метки — перепроверяются заново
  - Новые адреса из источников, которых нет в кэше — добавляются
  - `CACHE_TTL_HOURS = 0` отключает кэш (полная перезапись)
- Выделена функция `_load_cache()` → возвращает `(fresh_by_key, stale)`
- Выделена функция `_ping_batch()` — переиспользуется для stale и новых адресов
- Переход с `datetime.utcnow()` на `datetime.now(timezone.utc)` (timezone-aware)

### Added — Module 2 (tester.py)
- **TTL перепроверки** (`RETEST_TTL_HOURS = 3`):
  - Свежие viable-прокси пропускаются без повторного теста скорости
  - Если уже достаточно свежих viable ≥ TARGET_VIABLE — тестирование не запускается
- **Счётчик неудач** (`FAIL_EVICT_COUNT = 3`):
  - Каждый провал теста скорости увеличивает `fail_count` в JSON
  - При `fail_count >= FAIL_EVICT_COUNT` прокси удаляется из `viable_proxies.json`
  - Успешный тест сбрасывает счётчик в 0
- В таблице результатов добавлен столбец **«Неудач»** (жёлтый если > 0)
- Выделены функции: `_load_viable()`, `_is_stale()`, `_evict_failures()`, `_save_and_print()`

### Changed
- `tested_at` теперь timezone-aware ISO 8601

---

## [1.0.0] — 2025-03-18 · Первый релиз

### Added

#### Структура проекта
- Три независимых модуля в отдельных папках
- `main.py` — единый pipeline + CLI (`--module 1/2/3`)
- `requirements.txt`
- `README.md`
- `install.py` — самораспаковывающийся Python-скрипт

#### Module 1 — Proxy Collector (`module1_collector/collector.py`)
- HTML-парсинг таблиц прокси через BeautifulSoup4 + lxml
  - Поддержка пагинации через CSS-селектор следующей страницы
  - Источники: `free-proxy-list.net`, `sslproxies.org`, `hidemy.name`
- Скачивание текстовых файлов IP:PORT (формат `ip:port` построчно)
  - Источники: ProxyScrape API (HTTP/SOCKS4/SOCKS5), GitHub TheSpeedX
- JSON API с пагинацией
  - Источники: GeoNode proxylist API
- Дедупликация по ключу `ip:port`
- Параллельный TCP ping-тест (40 воркеров, ThreadPoolExecutor)
  - Прогресс-бар в реальном времени через `\r` overwrite
  - Таймаут: 3 секунды на попытку
- Выход: `proxy_list.json` отсортированный по пингу

#### Module 2 — Speed Tester (`module2_tester/tester.py`)
- Пакетная обработка: батчи по 10 адресов
- Параллельное тестирование: 2 прокси одновременно
- Двухэтапный тест: замер задержки (HEAD) + замер скорости (скачивание 2МБ)
- Fallback: 3 тестовых URL для скачивания
- Порог YouTube: 5 Мбит/с (настраивается `MIN_SPEED_MBPS`)
- Остановка по достижении TARGET_VIABLE подходящих прокси
- Live-обновление прогресса в CLI (overwrite строки)
- Итоговая таблица: IP, тип, скорость, задержка

#### Module 3 — Proxy Connector (`module3_connector/connector.py`)
- Интерактивное меню CLI с нумерованным списком прокси
- Установка системного прокси Windows тремя методами с fallback:
  1. `winreg` — запись в реестр HKCU (основной метод)
  2. PowerShell `Set-ItemProperty` (fallback)
  3. `netsh winhttp import proxy source=ie` (синхронизация WinHTTP)
- Правильный формат для SOCKS: `socks=ip:port`
- `ProxyOverride` для исключения локальных адресов
- Отключение прокси: команда `0`
- Статус текущего прокси: команда `s`
- Лог всех действий в `connection_log.txt`
- Предупреждение об ограничениях SOCKS на Windows

---

## Планируемые улучшения (Roadmap)

- [ ] Проверка доступности конкретных сайтов через прокси (YouTube, Google)
- [ ] Автоматическая ротация прокси при падении скорости
- [ ] Поддержка macOS (`networksetup`) и Linux (`gsettings`)
- [ ] GUI-версия на Tkinter или PyQt
- [ ] Шифрование `viable_proxies.json` (опционально)
- [ ] Уведомления (Windows Toast) при нахождении быстрого прокси
- [ ] Экспорт в форматы: PAC-файл, Proxychains конфиг
