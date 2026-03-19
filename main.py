"""
VPN/PROXY MANAGER — Главный запуск
===================================
Запускает модули по отдельности или как единый pipeline.

Использование:
  python main.py              — полный pipeline (1 → 2 → 3)
  python main.py --module 1  — только сборка прокси
  python main.py --module 2  — только тест скорости
  python main.py --module 3  — только подключение
  python main.py --help      — справка
"""

import os
import sys
import argparse

# ─── ANSI ────────────────────────────────────────────────────────────────────
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

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"
C = "\033[96m"; B = "\033[1m"; RS = "\033[0m"; DIM = "\033[2m"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _add_module_paths():
    for mod in ("module1_collector", "module2_tester", "module3_connector"):
        path = os.path.join(BASE_DIR, mod)
        if path not in sys.path:
            sys.path.insert(0, path)


def pipeline_banner():
    print(f"""
{C}{B}╔══════════════════════════════════════════════════╗
║   VPN / PROXY MANAGER  —  CLI Tool              ║
║   Module 1: Collector  →  2: Tester  →  3: Connect ║
╚══════════════════════════════════════════════════╝{RS}
""")


def run_module(num: str):
    """Запуск одного конкретного модуля."""
    _add_module_paths()

    if num == "1":
        print(f"\n{B}{'═'*50}{RS}")
        print(f"  {C}МОДУЛЬ 1{RS} — Сборщик прокси")
        print(f"{B}{'═'*50}{RS}\n")
        from collector import collect_all
        collect_all()

    elif num == "2":
        print(f"\n{B}{'═'*50}{RS}")
        print(f"  {C}МОДУЛЬ 2{RS} — Тест скорости")
        print(f"{B}{'═'*50}{RS}\n")
        from tester import find_viable
        find_viable()

    elif num == "3":
        print(f"\n{B}{'═'*50}{RS}")
        print(f"  {C}МОДУЛЬ 3{RS} — Подключение прокси")
        print(f"{B}{'═'*50}{RS}\n")
        from connector import main as connect_main
        connect_main()


def run_pipeline():
    """Запуск всех трёх модулей последовательно."""
    pipeline_banner()
    _add_module_paths()

    # ── Шаг 1: Сбор ──────────────────────────────────────────
    print(f"\n{C}{B}▶ ШАГ 1 / 3 — СБОРКА ПРОКСИ{RS}")
    print(f"{DIM}{'─'*50}{RS}\n")
    from collector import collect_all
    results = collect_all()

    if not results:
        print(f"\n{R}Модуль 1 не нашёл живых прокси. Завершение.{RS}\n")
        sys.exit(1)

    print(f"\n{G}✔ Шаг 1 завершён. Живых: {len(results)}{RS}")
    _pause("Нажмите Enter для запуска Модуля 2 (тест скорости)…")

    # ── Шаг 2: Тест скорости ─────────────────────────────────
    print(f"\n{C}{B}▶ ШАГ 2 / 3 — ТЕСТ СКОРОСТИ{RS}")
    print(f"{DIM}{'─'*50}{RS}\n")
    from tester import find_viable
    viable = find_viable()

    if not viable:
        print(f"\n{Y}Модуль 2 не нашёл подходящих прокси.{RS}")
        print(f"{DIM}Попробуйте снова запустить Модуль 1 для обновления списка.{RS}\n")
        sys.exit(1)

    print(f"\n{G}✔ Шаг 2 завершён. Подходящих: {len(viable)}{RS}")
    _pause("Нажмите Enter для запуска Модуля 3 (выбор и подключение)…")

    # ── Шаг 3: Подключение ───────────────────────────────────
    print(f"\n{C}{B}▶ ШАГ 3 / 3 — ПОДКЛЮЧЕНИЕ{RS}")
    print(f"{DIM}{'─'*50}{RS}\n")
    from connector import main as connect_main
    connect_main()


def _pause(msg: str):
    try:
        input(f"\n  {DIM}{msg}{RS}")
    except (KeyboardInterrupt, EOFError):
        print(f"\n{Y}Прерывание. Выход.{RS}")
        sys.exit(0)


# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="vpn-manager",
        description="CLI VPN/Proxy Manager — сбор, тест и подключение прокси",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{B}Примеры:{RS}
  python main.py               # Полный pipeline: 1 → 2 → 3
  python main.py --module 1    # Только сбор прокси
  python main.py --module 2    # Только тест скорости
  python main.py --module 3    # Только выбор и подключение

{B}Модули:{RS}
  1 — collector.py  →  module1_collector/output/proxy_list.json
  2 — tester.py     →  module2_tester/output/viable_proxies.json
  3 — connector.py  →  module3_connector/output/connection_log.txt
        """
    )
    parser.add_argument(
        "--module", "-m",
        choices=["1", "2", "3"],
        metavar="N",
        help="Запустить только модуль N (1, 2 или 3)"
    )
    args = parser.parse_args()

    if args.module:
        run_module(args.module)
    else:
        run_pipeline()


if __name__ == "__main__":
    main()
