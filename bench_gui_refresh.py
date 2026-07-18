"""Quick GUI refresh timing (run locally: python3 bench_gui_refresh.py)."""
from __future__ import annotations

import time

from simulation_gui import MainWindow


def ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0


def main() -> None:
    t0 = time.perf_counter()
    w = MainWindow()
    build_ms = ms(t0)
    w.root.update_idletasks()

    tab_ms: list[float] = []
    for i in range(7):
        t1 = time.perf_counter()
        w._select_main_tab(i)
        w.root.update_idletasks()
        tab_ms.append(ms(t1))

    t2 = time.perf_counter()
    w._refresh_run_config_preview_impl()
    w.root.update_idletasks()
    run_preview_ms = ms(t2)

    w.root.destroy()
    print(f"MainWindow build: {build_ms:.1f} ms")
    print("Tab switch (first pass, includes lazy hydrate):")
    for i, t in enumerate(tab_ms):
        print(f"  tab {i}: {t:.1f} ms")
    print(f"Run config preview refresh: {run_preview_ms:.1f} ms")


if __name__ == "__main__":
    main()
